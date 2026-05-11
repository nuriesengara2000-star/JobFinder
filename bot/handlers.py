import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config import PAGE_SIZE
from db.database import AsyncSessionLocal
from db.models import Application, Job, SavedJob
from services.analyzer import get_skill_gaps
from services.generator import generate_cover_letter
from services.matcher import get_top_jobs
from services.scraper import JobListing
from services.users import get_or_create_user, profile_to_dict

logger = logging.getLogger(__name__)
router = Router()

# ---------------------------------------------------------------------------
# Pagination state — maps telegram_id → ordered list of job IDs (score desc).
# In-memory: resets on bot restart. Users just run /jobs again.
# ---------------------------------------------------------------------------
_user_job_queue: dict[int, list[int]] = {}


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _score_emoji(score: int) -> str:
    if score >= 80:
        return "🔥"
    if score >= 60:
        return "✅"
    return "🔶"


def _bullet_list(items: list[str], fallback: str = "—") -> str:
    if not items:
        return f"  • {fallback}"
    return "\n".join(f"  • {item}" for item in items)


def _format_job_card(job_data: dict) -> str:
    job: Job = job_data["job"]
    score: int = job_data["score"]
    explanation: str = job_data["explanation"] or "No explanation available."
    matching: list[str] = job_data["matching_skills"] or []
    missing: list[str] = job_data["missing_skills"] or []

    return (
        f"{_score_emoji(score)} <b>{job.title}</b> @ <b>{job.company}</b>\n\n"
        f"📊 Score: <b>{score}/100</b>\n"
        f"<i>{explanation}</i>\n\n"
        f"✅ <b>Match:</b>\n{_bullet_list(matching)}\n\n"
        f"❌ <b>Missing:</b>\n{_bullet_list(missing, fallback='None')}"
    )


def _job_keyboard(job_id: int, job_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 Cover Letter", callback_data=f"cover:{job_id}"),
                InlineKeyboardButton(text="🔗 Open Job", url=job_link),
            ],
            [
                InlineKeyboardButton(text="⭐ Save Job", callback_data=f"save:{job_id}"),
                InlineKeyboardButton(text="⏭ Skip", callback_data=f"skip:{job_id}"),
            ],
        ]
    )


def _next_page_keyboard(next_offset: int, remaining: int) -> InlineKeyboardMarkup:
    label = f"⏩ Next {min(remaining, PAGE_SIZE)} jobs"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"jobs_next:{next_offset}")]
        ]
    )


# ---------------------------------------------------------------------------
# Page sender — shared by /jobs and the jobs_next callback
# ---------------------------------------------------------------------------

async def _send_page(target: Message, session, job_ids: list[int], offset: int) -> None:
    """
    Sends one page of job cards to `target` (a Message object).
    Appends a "Next" navigation button when more jobs remain.
    """
    page_ids = job_ids[offset : offset + PAGE_SIZE]
    if not page_ids:
        await target.answer("No more jobs to show.")
        return

    # Fetch the page from DB; preserve the sorted order from job_ids
    result = await session.execute(select(Job).where(Job.id.in_(page_ids)))
    jobs_by_id: dict[int, Job] = {j.id: j for j in result.scalars().all()}

    for job_id in page_ids:
        db_job = jobs_by_id.get(job_id)
        if db_job is None:
            logger.warning("Job id=%d missing from DB during pagination", job_id)
            continue
        job_data = {
            "job": db_job,
            "score": db_job.score or 0,
            "explanation": db_job.explanation or "",
            "matching_skills": db_job.matching_skills or [],
            "missing_skills": db_job.missing_skills or [],
        }
        await target.answer(_format_job_card(job_data), reply_markup=_job_keyboard(db_job.id, db_job.link))

    next_offset = offset + PAGE_SIZE
    if next_offset < len(job_ids):
        remaining = len(job_ids) - next_offset
        await target.answer(
            f"<i>Showing {offset + 1}–{offset + len(page_ids)} of {len(job_ids)} matches.</i>",
            reply_markup=_next_page_keyboard(next_offset, remaining),
        )


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id)
        await session.commit()

    skills_preview = ", ".join(user.skills[:5])
    if len(user.skills) > 5:
        skills_preview += "…"

    text = (
        "👋 <b>Welcome to Job AI Agent!</b>\n\n"
        "I score job listings against your profile with AI "
        "and write tailored cover letters on demand.\n\n"
        "<b>Commands:</b>\n"
        "• /jobs — Find and rank your top matching jobs\n"
        "• /skills — See your most common skill gaps\n"
        "• /find — Send your resume → AI agent fetches real hh.kz vacancies\n\n"
        f"<b>Your profile:</b> {user.level.title()}\n"
        f"<b>Skills:</b> {skills_preview}"
    )
    await message.answer(text)


# ---------------------------------------------------------------------------
# /jobs
# ---------------------------------------------------------------------------

@router.message(Command("jobs"))
async def cmd_jobs(message: Message) -> None:
    status = await message.answer(
        "🔍 Fetching and scoring jobs with AI…\n"
        "<i>Already-scored jobs load instantly; new ones take ~15 s.</i>"
    )

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id)
        profile = profile_to_dict(user)

        try:
            top_jobs = await get_top_jobs(session, profile)
        except Exception as exc:
            logger.exception("get_top_jobs failed for user %d", user.telegram_id)
            await status.edit_text(f"❌ Error while scoring jobs:\n<code>{exc}</code>")
            return

        await session.commit()

        if not top_jobs:
            await status.edit_text("😕 No scoreable jobs found. Try again later.")
            return

        # Store ordered job IDs for pagination; overwrite any previous session
        job_ids = [d["job"].id for d in top_jobs]
        _user_job_queue[message.from_user.id] = job_ids

        await status.edit_text(f"✅ Found <b>{len(job_ids)}</b> matches for your profile:")
        await _send_page(message, session, job_ids, offset=0)


# ---------------------------------------------------------------------------
# Pagination — Next page callback
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("jobs_next:"))
async def handle_jobs_next(callback: CallbackQuery) -> None:
    await callback.answer()

    offset = int(callback.data.split(":", 1)[1])
    telegram_id = callback.from_user.id

    job_ids = _user_job_queue.get(telegram_id)
    if not job_ids:
        await callback.message.answer(
            "⚠️ Session expired — please run /jobs again."
        )
        return

    # Remove the "Next" button from the nav message to prevent re-clicks
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    async with AsyncSessionLocal() as session:
        await _send_page(callback.message, session, job_ids, offset)


# ---------------------------------------------------------------------------
# /skills — skill gap analysis
# ---------------------------------------------------------------------------

@router.message(Command("skills"))
async def cmd_skills(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        gaps = await get_skill_gaps(session)

    if not gaps:
        await message.answer(
            "📊 No skill gap data yet.\n"
            "Run /jobs first so I can analyse which skills you're missing."
        )
        return

    lines = [
        f"  • <b>{skill.title()}</b> ({count} job{'s' if count > 1 else ''})"
        for skill, count in gaps
    ]
    text = "📈 <b>Skills to improve based on your top matches:</b>\n\n" + "\n".join(lines)
    await message.answer(text)


# ---------------------------------------------------------------------------
# Save Job callback
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("save:"))
async def handle_save_job(callback: CallbackQuery) -> None:
    job_id = int(callback.data.split(":", 1)[1])

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        saved = SavedJob(user_id=user.id, job_id=job_id)
        session.add(saved)
        try:
            await session.commit()
        except IntegrityError:
            # Unique constraint violation — user already saved this job
            await session.rollback()
            await callback.answer("Already saved ⭐", show_alert=False)
            return

    await callback.answer("Saved! ✅", show_alert=False)


# ---------------------------------------------------------------------------
# Skip callback — pure UX dismissal, no DB action
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("skip:"))
async def handle_skip_job(callback: CallbackQuery) -> None:
    await callback.answer("Skipped ⏭", show_alert=False)


# ---------------------------------------------------------------------------
# Cover letter callback
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("cover:"))
async def handle_cover_letter(callback: CallbackQuery) -> None:
    await callback.answer("Generating your cover letter…")

    job_id = int(callback.data.split(":", 1)[1])
    telegram_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, telegram_id)

        result = await session.execute(select(Job).where(Job.id == job_id))
        db_job: Job | None = result.scalar_one_or_none()

        if db_job is None:
            await callback.message.answer("❌ Job not found. Please run /jobs again.")
            return

        profile = profile_to_dict(user)
        # Capture fields now — session will close before we send the message
        job_title = db_job.title
        job_company = db_job.company
        listing = JobListing(
            title=db_job.title,
            company=db_job.company,
            description=db_job.description,
            link=db_job.link,
        )

        await callback.message.answer("✍️ Writing your cover letter…")

        try:
            letter = await generate_cover_letter(listing, profile)
        except Exception as exc:
            logger.exception(
                "generate_cover_letter failed for job_id=%d user=%d", job_id, telegram_id
            )
            await callback.message.answer(
                f"❌ Failed to generate cover letter:\n<code>{exc}</code>"
            )
            return

        session.add(Application(user_id=user.id, job_id=db_job.id, cover_letter=letter))
        await session.commit()

    await callback.message.answer(
        f"✍️ <b>Cover Letter — {job_title} @ {job_company}</b>\n\n{letter}"
    )
