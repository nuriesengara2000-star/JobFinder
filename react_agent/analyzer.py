"""Per-job fit analysis: compares the candidate's resume against a vacancy and
emits matching skills, missing skills, a 0-100 fit score, and a 1-sentence verdict.

The sync ``analyze_fit`` is the single primitive. The async ``analyze_jobs``
fans it out across many jobs in a thread pool so the bot can call it without
blocking the event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from openai import OpenAI

LOG = logging.getLogger(__name__)

_client: OpenAI | None = None


def _openai() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _client = OpenAI(api_key=api_key)
    return _client


_SYSTEM_PROMPT = """\
You are a job-fit analyzer. Compare a candidate to ONE job posting and reply
with STRICT JSON only — no prose.

Output keys (all required):
  "fit_score":        integer 0-100 — your honest assessment.
                      90+ = excellent, 70-89 = strong, 50-69 = moderate,
                      <50 = poor. Be calibrated, not generous.
  "matching_skills":  array of skills the candidate HAS that the job mentions
                      or clearly implies. Use the candidate's own skill names.
                      Treat near-equivalents as matches (Postgres ≈ PostgreSQL,
                      JS ≈ JavaScript, Node ≈ Node.js).
  "missing_skills":   array of SPECIFIC skills mentioned in the job text that
                      the candidate does NOT have. Be concrete (e.g. "Supabase",
                      "Kubernetes", "gRPC"). Do NOT list vague things like
                      "backend experience" or "team player".
  "verdict":          ONE short sentence (≤140 chars) — honest verdict.
                      Use the same language as the candidate's resume
                      (Russian if resume is Russian, English otherwise).

If the job description is too short or generic to evaluate, return fit_score 50,
empty arrays, and verdict "Insufficient job description to evaluate."
"""


def analyze_fit(
    skills: list[str],
    desired_role: str,
    experience_level: str,
    job: dict[str, Any],
) -> dict[str, Any]:
    """Synchronous fit analysis for a single job. Returns dict with keys:
    fit_score, matching_skills, missing_skills, verdict."""
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    user_payload = {
        "candidate": {
            "skills": skills,
            "desired_role": desired_role,
            "experience_level": experience_level,
        },
        "job": {
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "description": (job.get("requirements") or "")[:1500],
        },
    }

    try:
        resp = _openai().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        LOG.exception("analyze_fit LLM call failed")
        return _fallback("LLM error: " + repr(exc))

    raw = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        LOG.warning("analyze_fit: bad JSON: %r", raw)
        return _fallback("Bad JSON from analyzer.")

    return {
        "fit_score": _clamp_score(data.get("fit_score")),
        "matching_skills": _clean_list(data.get("matching_skills")),
        "missing_skills": _clean_list(data.get("missing_skills")),
        "verdict": str(data.get("verdict") or "").strip()[:200] or "—",
    }


async def analyze_jobs(
    skills: list[str],
    desired_role: str,
    experience_level: str,
    jobs: list[dict[str, Any]],
    max_concurrency: int = 5,
) -> list[dict[str, Any]]:
    """Run ``analyze_fit`` on all jobs concurrently (bounded). Returns the
    original jobs with an extra ``analysis`` key on each."""
    if not jobs:
        return []

    sem = asyncio.Semaphore(max_concurrency)

    async def _one(job: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            analysis = await asyncio.to_thread(
                analyze_fit, skills, desired_role, experience_level, job
            )
        return {**job, "analysis": analysis}

    return await asyncio.gather(*[_one(j) for j in jobs])


# ---------------------------------------------------------------- helpers

def _clamp_score(v: Any) -> int:
    try:
        return max(0, min(100, int(v)))
    except (TypeError, ValueError):
        return 50


def _clean_list(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in v:
        s = str(item).strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def _fallback(reason: str) -> dict[str, Any]:
    return {
        "fit_score": 0,
        "matching_skills": [],
        "missing_skills": [],
        "verdict": f"⚠ {reason}",
    }
