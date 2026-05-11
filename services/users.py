import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserProfile

logger = logging.getLogger(__name__)

# Default profile applied to every new Telegram user.
# Future: replace with an onboarding flow (/setup command).
_DEFAULT_SKILLS: list[str] = [
    "Python",
    "Machine Learning",
    "LLMs",
    "FastAPI",
    "SQLAlchemy",
    "OpenAI API",
    "Prompt Engineering",
    "PostgreSQL",
]
_DEFAULT_LEVEL: str = "junior AI engineer"


async def get_or_create_user(session: AsyncSession, telegram_id: int) -> UserProfile:
    """
    Fetches the UserProfile for the given Telegram user ID.
    Creates one with default values on first call.
    """
    result = await session.execute(
        select(UserProfile).where(UserProfile.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = UserProfile(
            telegram_id=telegram_id,
            skills=list(_DEFAULT_SKILLS),
            level=_DEFAULT_LEVEL,
        )
        session.add(user)
        await session.flush()
        logger.info("Created UserProfile for telegram_id=%d", telegram_id)

    return user


def profile_to_dict(user: UserProfile) -> dict:
    """Converts a UserProfile ORM object to the dict format expected by services."""
    return {
        "skills": user.skills if isinstance(user.skills, list) else [],
        "level": user.level,
    }
