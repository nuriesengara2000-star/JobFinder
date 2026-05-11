import asyncio
import logging

from openai import APITimeoutError, AsyncOpenAI, RateLimitError

from config import OPENAI_API_KEY, OPENAI_MODEL
from services.scraper import JobListing

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def _call_openai(job: JobListing, skills_str: str, level: str) -> str:
    prompt = f"""Write a short professional cover letter for this job application.

Position: {job.title}
Company: {job.company}
Job description: {job.description}

Candidate:
- Role: {level}
- Key skills: {skills_str}

Requirements:
- Maximum 120 words
- Tone: confident, enthusiastic, professional — junior AI engineer voice
- Do NOT include placeholders like [Your Name], [Date], or [Company Address]
- Do NOT open with "Dear Hiring Manager" — begin with an engaging first line
- Be specific to this exact role and company
- Naturally weave in the most relevant candidate skills
- End with a forward-looking sentence about contributing to the team"""

    response = await _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=350,
    )
    return response.choices[0].message.content.strip()


async def generate_cover_letter(
    job: JobListing,
    user_profile: dict,
    max_retries: int = 3,
) -> str:
    """
    Generates a short, tailored cover letter (~120 words).

    Retries up to max_retries times on rate limits or timeouts.
    Other OpenAI errors propagate immediately so the caller can handle them.

    Stateless — persisting the result to Application is the caller's responsibility.
    """
    skills_str = ", ".join(user_profile.get("skills", []))
    level = user_profile.get("level", "junior AI engineer")

    delay = 1.0
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            letter = await _call_openai(job, skills_str, level)
            logger.info(
                "Cover letter generated for %r at %r (%d chars)",
                job.title,
                job.company,
                len(letter),
            )
            return letter

        except (RateLimitError, APITimeoutError) as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                break
            wait = delay * (2 ** attempt)
            logger.warning(
                "OpenAI %s on cover letter for %r — retrying in %.1fs (attempt %d/%d)",
                type(exc).__name__,
                job.title,
                wait,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(wait)

        except Exception:
            # Non-transient error — don't retry, let the handler report it
            logger.exception("Non-retryable error generating cover letter for %r", job.title)
            raise

    logger.error(
        "Cover letter generation failed for %r after %d attempts: %s",
        job.title,
        max_retries,
        last_exc,
    )
    raise last_exc
