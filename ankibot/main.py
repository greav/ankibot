import logging
import os

from aiogram import Bot, Dispatcher

from .application.user_state import UserStateManager
from .config import load_config
from .infra.anki_api_client import AnkiApiClientImpl
from .infra.cookie_storage import InMemoryCookieStorage
from .infra.logger import configure_root_logger
from .presentation import commands, handlers

logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config(os.getenv("CONFIG_PATH", "./configs/config.yaml"))

    configure_root_logger(config.logger)

    # Initialize dependencies
    cookie_storage = InMemoryCookieStorage()
    anki_client = AnkiApiClientImpl(cookie_storage)
    user_state_manager = UserStateManager()

    # Initialize handlers with dependencies
    handlers.init_handlers(anki_client, user_state_manager, config.anki)

    dp = Dispatcher()
    bot = Bot(token=config.bot.token)

    # Set bot commands
    await commands.set_commands(bot)

    dp.include_router(handlers.router)

    logger.info("Bot has started")
    await dp.start_polling(bot)
