import logging
import os

from aiogram import Bot, Dispatcher

from ankibot.infra.logger import configure_root_logger
from ankibot.presentation.handlers import start

from .config import load_config

logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config(os.getenv("CONFIG_PATH", "./configs/config.yaml"))

    configure_root_logger(config.logger)

    dp = Dispatcher()
    bot = Bot(token=config.bot.token)

    dp.include_router(start.router)

    await dp.start_polling(bot)

    logger.info("Bot has started")
