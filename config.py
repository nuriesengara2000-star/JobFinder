import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


BOT_TOKEN: str = _require("BOT_TOKEN")
OPENAI_API_KEY: str = _require("OPENAI_API_KEY")
DATABASE_URL: str = _require("DATABASE_URL")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TOP_JOBS_COUNT: int = 5

# Maximum concurrent OpenAI scoring requests (respects API rate limits)
SCORING_CONCURRENCY: int = int(os.getenv("SCORING_CONCURRENCY", "3"))

# How many job cards to send per page in Telegram
PAGE_SIZE: int = int(os.getenv("PAGE_SIZE", "3"))
