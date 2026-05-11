import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Job

logger = logging.getLogger(__name__)


async def get_skill_gaps(session: AsyncSession, top_n: int = 5) -> list[tuple[str, int]]:
    """
    Aggregates missing_skills from all scored jobs in the DB.

    Normalisation rules applied before counting:
    - Each skill is lowercased and stripped of whitespace
    - Skills are deduplicated *per job* so a job that lists "Docker" twice
      still contributes a count of 1 for that skill

    Returns the top N (skill, count) pairs, sorted descending by frequency.
    """
    result = await session.execute(
        select(Job.missing_skills).where(Job.missing_skills.isnot(None))
    )
    rows = result.scalars().all()

    counter: Counter[str] = Counter()
    for skills_list in rows:
        if not isinstance(skills_list, list):
            continue
        # Deduplicate per job before counting
        unique_for_job: set[str] = set()
        for skill in skills_list:
            normalized = str(skill).strip().lower()
            if normalized:
                unique_for_job.add(normalized)
        for skill in unique_for_job:
            counter[skill] += 1

    logger.info(
        "Skill gap analysis: %d unique skills found across %d scored jobs",
        len(counter),
        len(rows),
    )
    return counter.most_common(top_n)
