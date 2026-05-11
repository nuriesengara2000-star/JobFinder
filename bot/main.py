import asyncio
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so that sibling packages
# (config, db, services) resolve correctly regardless of how this
# script is invoked (python bot/main.py  OR  python -m bot.main).
# ---------------------------------------------------------------------------
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import db.models  # noqa: F401 — registers all ORM models with Base.metadata
from bot.agent_handlers import router as react_agent_router
from bot.handlers import router
from config import BOT_TOKEN
from db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-32s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()
    logger.info("Database tables verified / created")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    dp.include_router(react_agent_router)

    logger.info("Bot is starting — press Ctrl+C to stop")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
