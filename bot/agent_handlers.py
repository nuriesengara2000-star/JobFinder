"""Telegram glue for the multi-source ReAct job-search agent.

Flow:
    /find  → bot asks for resume (text OR PDF/DOCX/TXT file)
    user replies (text message OR document) →
       1. resume text is extracted (bytes → text for files)
       2. JobSearchAgent runs in a worker thread, queries 4 job sources
       3. analyzer.analyze_jobs scores each collected vacancy against the resume
       4. bot sends one enriched card per job (title, fit %, match/missing, link)
    /cancel → aborts the flow
"""

from __future__ import annotations

import asyncio
import io
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.resume_io import ResumeReadError, extract_text
from react_agent.agent import JobSearchAgent
from react_agent.analyzer import analyze_jobs

logger = logging.getLogger(__name__)
router = Router(name="react_agent")


class FindJobsFlow(StatesGroup):
    waiting_for_resume = State()


# How many of the agent's collected jobs to enrich with fit analysis.
TOP_ANALYZE = 10
TG_LIMIT = 3800


# ---------------------------------------------------------------------------
# /find — start the flow
# ---------------------------------------------------------------------------

@router.message(Command("find"))
async def cmd_find(message: Message, state: FSMContext) -> None:
    await state.set_state(FindJobsFlow.waiting_for_resume)
    await message.answer(
        "🤖 <b>AI Job Search</b>\n\n"
        "Пришли резюме одним из двух способов:\n"
        "  • <b>Текстом</b> — просто скопируй и отправь\n"
        "  • <b>Файлом</b> — PDF, DOCX или TXT\n\n"
        "Я разберу его, найду реальные вакансии в 4 источниках "
        "(<b>hh.kz · LinkedIn · RemoteOK · We Work Remotely</b>) "
        "и для каждой посчитаю % соответствия + чего не хватает.\n\n"
        "Чтобы отменить — /cancel"
    )


# ---------------------------------------------------------------------------
# /cancel — works only inside the flow
# ---------------------------------------------------------------------------

@router.message(Command("cancel"), StateFilter(FindJobsFlow.waiting_for_resume))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Поиск отменён.")


# ---------------------------------------------------------------------------
# Resume — text version
# ---------------------------------------------------------------------------

@router.message(StateFilter(FindJobsFlow.waiting_for_resume), F.text)
async def handle_resume_text(message: Message, state: FSMContext) -> None:
    resume = (message.text or "").strip()
    await state.clear()
    if len(resume) < 30:
        await message.answer(
            "⚠️ Резюме слишком короткое. Запусти /find и пришли полный текст или файл."
        )
        return
    await _run_pipeline(message, resume)


# ---------------------------------------------------------------------------
# Resume — document version (PDF / DOCX / TXT)
# ---------------------------------------------------------------------------

@router.message(StateFilter(FindJobsFlow.waiting_for_resume), F.document)
async def handle_resume_document(message: Message, state: FSMContext, bot: Bot) -> None:
    doc = message.document
    await state.clear()

    if doc is None:
        await message.answer("⚠️ Не вижу прикреплённый файл. Запусти /find ещё раз.")
        return

    name = doc.file_name or "resume"
    mime = doc.mime_type or ""
    if doc.file_size and doc.file_size > 5 * 1024 * 1024:
        await message.answer("⚠️ Файл больше 5 MB — урежь и пришли снова.")
        return

    status = await message.answer(f"📥 Качаю файл <code>{escape(name)}</code>…")

    try:
        buf = io.BytesIO()
        await bot.download(doc, destination=buf)
        data = buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Telegram download failed")
        await status.edit_text(f"❌ Не получилось скачать файл:\n<code>{escape(str(exc))}</code>")
        return

    try:
        resume = extract_text(data, filename=name, mime_type=mime).strip()
    except ResumeReadError as exc:
        await status.edit_text(f"❌ {escape(str(exc))}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Resume extraction failed")
        await status.edit_text(f"❌ Не удалось разобрать файл: <code>{escape(str(exc))}</code>")
        return

    if len(resume) < 30:
        await status.edit_text(
            "⚠️ В файле почти нет текста. Если это скан — пришли DOCX или текстовую версию."
        )
        return

    await status.edit_text(
        f"✅ Файл прочитан (<b>{len(resume):,}</b> символов). Запускаю поиск…"
    )
    await _run_pipeline(message, resume)


# ---------------------------------------------------------------------------
# Fallback inside the flow (sticker, voice, photo, etc.)
# ---------------------------------------------------------------------------

@router.message(StateFilter(FindJobsFlow.waiting_for_resume))
async def handle_other(message: Message) -> None:
    await message.answer(
        "⚠️ Жду <b>текст резюме</b> или <b>файл</b> (PDF/DOCX/TXT). "
        "Или /cancel."
    )


# ===========================================================================
# Pipeline: agent → analyzer → enriched cards
# ===========================================================================

async def _run_pipeline(message: Message, resume: str) -> None:
    status = await message.answer(
        "🔎 Запускаю ReAct-агента — парсю резюме и ищу вакансии "
        "(hh.kz + LinkedIn + RemoteOK + We Work Remotely)…\n"
        "<i>~30–60 секунд.</i>"
    )

    # 1. Run the ReAct agent off the event loop (sync OpenAI + requests).
    try:
        agent = JobSearchAgent()
        await asyncio.to_thread(agent.run, resume)
    except Exception as exc:  # noqa: BLE001
        logger.exception("ReAct agent crashed for user %s", message.from_user.id)
        await status.edit_text(f"❌ Агент упал:\n<code>{escape(str(exc))}</code>")
        return

    jobs = agent.collected_jobs[:TOP_ANALYZE]
    profile = agent.parsed_resume or {}

    if not jobs:
        await status.edit_text(
            "😕 Агент не нашёл подходящих вакансий. "
            "Попробуй уточнить роль/навыки в резюме и запусти /find снова."
        )
        return

    await status.edit_text(
        f"✅ Найдено <b>{len(jobs)}</b> вакансий. Считаю соответствие…\n"
        "<i>~10–20 секунд.</i>"
    )

    # 2. Per-job fit analysis (parallel, bounded).
    try:
        enriched = await analyze_jobs(
            skills=profile.get("skills") or [],
            desired_role=profile.get("desired_role") or "",
            experience_level=profile.get("experience_level") or "",
            jobs=jobs,
            max_concurrency=5,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("analyze_jobs failed")
        await status.edit_text(f"❌ Анализ упал:\n<code>{escape(str(exc))}</code>")
        return

    # 3. Sort by fit_score desc, render cards, send.
    enriched.sort(key=lambda j: j.get("analysis", {}).get("fit_score", 0), reverse=True)
    cards = [_render_card(i + 1, j) for i, j in enumerate(enriched)]

    summary = _render_summary(profile, enriched)
    await status.edit_text(summary)

    for batch in _batch_for_telegram(cards):
        await message.answer(batch, disable_web_page_preview=True)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_SOURCE_LABEL = {
    "hh": "hh.kz",
    "linkedin": "LinkedIn",
    "remoteok": "RemoteOK",
    "wwr": "WeWorkRemotely",
}


def _render_summary(profile: dict, enriched: list[dict]) -> str:
    role = profile.get("desired_role") or "—"
    level = profile.get("experience_level") or "—"
    skills = profile.get("skills") or []
    skills_preview = ", ".join(skills[:8]) + ("…" if len(skills) > 8 else "")
    avg = round(sum(j.get("analysis", {}).get("fit_score", 0) for j in enriched) / max(len(enriched), 1))
    return (
        f"✅ Готово. Найдено <b>{len(enriched)}</b> вакансий, средний fit-score "
        f"<b>{avg}/100</b>.\n\n"
        f"👤 <b>Роль:</b> {escape(role)} · <b>Уровень:</b> {escape(level)}\n"
        f"🛠 <b>Навыки:</b> {escape(skills_preview) or '—'}\n\n"
        "Карточки ниже отсортированы по соответствию ⬇️"
    )


def _score_emoji(score: int) -> str:
    if score >= 85:
        return "🔥"
    if score >= 70:
        return "✅"
    if score >= 50:
        return "🟡"
    return "🔻"


def _render_card(idx: int, job: dict) -> str:
    a = job.get("analysis") or {}
    score = int(a.get("fit_score") or 0)
    matching = a.get("matching_skills") or []
    missing = a.get("missing_skills") or []
    verdict = a.get("verdict") or "—"

    title = escape((job.get("title") or "—").strip())
    company = escape((job.get("company") or "—").strip())
    src = _SOURCE_LABEL.get(job.get("source", ""), job.get("source", ""))
    salary = job.get("salary")
    url = job.get("url") or ""

    lines = [
        f"<b>{idx}. {title}</b> — {company}  <i>[{escape(src)}]</i>",
        f"{_score_emoji(score)} <b>Fit:</b> {score}/100",
    ]
    if salary:
        lines.append(f"💰 {escape(str(salary))}")
    if matching:
        lines.append("✅ <b>Match:</b> " + ", ".join(escape(s) for s in matching[:10]))
    if missing:
        lines.append("❌ <b>Need to learn:</b> " + ", ".join(escape(s) for s in missing[:10]))
    lines.append(f"💬 <i>{escape(verdict)}</i>")
    if url:
        lines.append(f'🔗 <a href="{escape(url)}">{escape(url)}</a>')
    return "\n".join(lines)


def _batch_for_telegram(cards: list[str], limit: int = TG_LIMIT) -> list[str]:
    """Pack rendered cards into Telegram-sized messages, one card per block."""
    out: list[str] = []
    buf = ""
    for card in cards:
        block = card + "\n\n"
        if len(buf) + len(block) > limit and buf:
            out.append(buf.rstrip())
            buf = block
        else:
            buf += block
    if buf:
        out.append(buf.rstrip())
    return out
