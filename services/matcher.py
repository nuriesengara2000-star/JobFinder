import asyncio
import json
import logging

from openai import APITimeoutError, AsyncOpenAI, RateLimitError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import OPENAI_API_KEY, OPENAI_MODEL, SCORING_CONCURRENCY, TOP_JOBS_COUNT
from db.models import Job
from services.scraper import JobListing, get_jobs

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Score stored when AI is temporarily unavailable. NOT persisted to DB so the
# job will be re-scored on the next request once the service recovers.
_FALLBACK_RESULT: dict = {
    "score": 50,
    "explanation": "Score temporarily unavailable — AI service returned an error.",
    "matching_skills": [],
    "missing_skills": [],
    "is_fallback": True,
}


# ---------------------------------------------------------------------------
# OpenAI call — single attempt, raises on any error
# ---------------------------------------------------------------------------

async def _call_openai(listing: JobListing, user_profile: dict) -> dict:
    skills_str = ", ".join(user_profile.get("skills", []))
    level = user_profile.get("level", "junior")

    prompt = f"""You are a senior technical recruiter. Score how well this candidate matches the job.

Candidate:
- Level: {level}
- Skills: {skills_str}

Job: {listing.title} at {listing.company}
Description: {listing.description}

Respond with valid JSON only, using this exact schema:
{{
  "score": <integer 0–100, based on skill overlap and seniority fit>,
  "explanation": "<one concise sentence summarising the overall match quality>",
  "matching_skills": ["<candidate skill that is relevant to this job>"],
  "missing_skills": ["<skill required by the job that the candidate lacks>"]
}}

Scoring guide:
- 80–100: excellent — most skills present, right seniority level
- 60–79: good — majority of skills covered, minor gaps
- 40–59: partial — some relevant skills, notable gaps
- 0–39: weak — significant skill or level mismatch

Both arrays must be lists of strings (empty list if none apply)."""

    response = await _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("OpenAI returned invalid JSON for %r: %.200s", listing.title, raw)
        raise ValueError(f"Invalid JSON from OpenAI: {raw[:100]}")

    return {
        "score": max(0, min(100, int(data.get("score") or 0))),
        "explanation": str(data.get("explanation") or "").strip(),
        "matching_skills": [str(s) for s in (data.get("matching_skills") or [])],
        "missing_skills": [str(s) for s in (data.get("missing_skills") or [])],
    }


# ---------------------------------------------------------------------------
# Retry wrapper — exponential backoff for transient errors only
# ---------------------------------------------------------------------------

async def _score_with_retry(listing: JobListing, user_profile: dict, max_retries: int = 3) -> dict:
    """
    Wraps _call_openai with retry logic.

    - RateLimitError / APITimeoutError → retry up to max_retries with exponential backoff
    - Other exceptions → log and return fallback immediately (not worth retrying)
    - Fallback results are marked with is_fallback=True so the caller skips DB persistence
    """
    delay = 1.0

    for attempt in range(max_retries):
        try:
            return await _call_openai(listing, user_profile)

        except (RateLimitError, APITimeoutError) as exc:
            if attempt == max_retries - 1:
                logger.warning(
                    "OpenAI %s for %r — all %d retries exhausted, using fallback",
                    type(exc).__name__,
                    listing.title,
                    max_retries,
                )
                return dict(_FALLBACK_RESULT)

            wait = delay * (2 ** attempt)
            logger.warning(
                "OpenAI %s for %r — retrying in %.1fs (attempt %d/%d)",
                type(exc).__name__,
                listing.title,
                wait,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(wait)

        except Exception as exc:
            logger.error(
                "Non-retryable OpenAI error for job %r: %s — using fallback",
                listing.title,
                exc,
            )
            return dict(_FALLBACK_RESULT)

    # Unreachable but satisfies the type checker
    return dict(_FALLBACK_RESULT)  # pragma: no cover


# ---------------------------------------------------------------------------
# Batch DB helpers
# ---------------------------------------------------------------------------

async def _batch_upsert_listings(session: AsyncSession, listings: list[JobListing]) -> list[Job]:
    """
    Inserts all scraped listings in one statement using ON CONFLICT DO NOTHING,
    then fetches all of them in a single SELECT.

    This replaces N individual SELECT+flush calls with 2 round-trips total,
    and eliminates race conditions on the unique(link) constraint.
    """
    if not listings:
        return []

    stmt = (
        pg_insert(Job)
        .values(
            [
                {
                    "title": l.title,
                    "company": l.company,
                    "description": l.description,
                    "link": l.link,
                }
                for l in listings
            ]
        )
        .on_conflict_do_nothing(index_elements=["link"])
    )
    await session.execute(stmt)

    links = [l.link for l in listings]
    result = await session.execute(select(Job).where(Job.link.in_(links)))
    db_jobs = list(result.scalars().all())

    logger.debug("Batch upsert: %d scraped → %d in DB", len(listings), len(db_jobs))
    return db_jobs


# ---------------------------------------------------------------------------
# Concurrent scoring — one task per unscored job, bounded by semaphore
# ---------------------------------------------------------------------------

async def _score_one(
    semaphore: asyncio.Semaphore,
    db_job: Job,
    user_profile: dict,
) -> dict:
    """Scores a single job under the shared concurrency semaphore."""
    async with semaphore:
        listing = JobListing(
            title=db_job.title,
            company=db_job.company,
            description=db_job.description,
            link=db_job.link,
        )
        return await _score_with_retry(listing, user_profile)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _job_to_dict(job: Job) -> dict:
    return {
        "job": job,
        "score": job.score or 0,
        "explanation": job.explanation or "",
        "matching_skills": job.matching_skills or [],
        "missing_skills": job.missing_skills or [],
    }


async def get_top_jobs(
    session: AsyncSession,
    user_profile: dict,
    top_n: int = TOP_JOBS_COUNT,
) -> list[dict]:
    """
    Full pipeline: scrape → batch-upsert → score new jobs concurrently (cached) → sort → top N.

    Cache behaviour: jobs with an existing score are never re-sent to OpenAI.
    Fallback scores (is_fallback=True) are shown in the current response but
    NOT persisted, so the job will be re-scored on the next /jobs call.

    Returns a list of dicts:
        {"job": Job, "score": int, "explanation": str,
         "matching_skills": list[str], "missing_skills": list[str]}
    """
    listings = await get_jobs()
    logger.info("Processing %d scraped listings", len(listings))

    db_jobs = await _batch_upsert_listings(session, listings)

    cached_jobs = [j for j in db_jobs if j.score is not None]
    unscored_jobs = [j for j in db_jobs if j.score is None]

    logger.info(
        "Cache: %d hits | to score: %d",
        len(cached_jobs),
        len(unscored_jobs),
    )

    # Score all unscored jobs concurrently, bounded to SCORING_CONCURRENCY
    if unscored_jobs:
        semaphore = asyncio.Semaphore(SCORING_CONCURRENCY)
        tasks = [_score_one(semaphore, job, user_profile) for job in unscored_jobs]
        score_results: list[dict] = await asyncio.gather(*tasks)

        newly_scored = fallbacks = 0
        for db_job, result in zip(unscored_jobs, score_results):
            if result.get("is_fallback"):
                # Don't mutate the ORM object — fallback is not cached
                fallbacks += 1
                continue
            db_job.score = result["score"]
            db_job.explanation = result["explanation"]
            db_job.matching_skills = result["matching_skills"]
            db_job.missing_skills = result["missing_skills"]
            newly_scored += 1

        logger.info(
            "Scoring complete — cached: %d | new: %d | fallbacks: %d",
            len(cached_jobs),
            newly_scored,
            fallbacks,
        )

    # Build result list: persisted scores from ORM objects + in-memory fallback entries
    result_dicts: list[dict] = [_job_to_dict(j) for j in cached_jobs]

    for db_job, result in zip(unscored_jobs, score_results if unscored_jobs else []):
        if result.get("is_fallback"):
            # Include in response with fallback data but don't touch the ORM object
            result_dicts.append(
                {
                    "job": db_job,
                    "score": result["score"],
                    "explanation": result["explanation"],
                    "matching_skills": [],
                    "missing_skills": [],
                }
            )
        else:
            result_dicts.append(_job_to_dict(db_job))

    result_dicts.sort(key=lambda d: d["score"], reverse=True)
    return result_dicts[:top_n]
