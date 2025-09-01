import logging
import os

from aiogram import Bot, Dispatcher

from .application.user_state import UserStateManager
from .config import load_config
from .infra.anki_api_client import AnkiApiClientImpl
from .infra.cookie_storage import InMemoryCookieStorage
from .infra.logger import configure_root_logger
from .infra.openai_client import OpenAIClientImpl
from .presentation import commands, handlers
from .presentation.middleware import AdminOnlyMiddleware

logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config(os.getenv("CONFIG_PATH", "./configs/config.yaml"))

    configure_root_logger(config.logger)

    # Initialize dependencies
    cookie_storage = InMemoryCookieStorage()
    anki_client = AnkiApiClientImpl(cookie_storage)
    openai_client = OpenAIClientImpl(config.openai.api_key)
    user_state_manager = UserStateManager()

    # Initialize handlers with dependencies
    handlers.init_handlers(anki_client, openai_client, user_state_manager, config.anki, config.openai)

    dp = Dispatcher()
    bot = Bot(token=config.bot.token)

    # Set up admin-only middleware
    admin_middleware = AdminOnlyMiddleware(config.bot.admin_user_ids or [])
    dp.message.middleware(admin_middleware)

    # Set bot commands
    await commands.set_commands(bot)

    dp.include_router(handlers.router)

    logger.info("Bot has started")
    await dp.start_polling(bot)
