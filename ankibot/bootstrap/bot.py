import logging
import os

import httpx
from aiogram import Bot, Dispatcher

from ankibot.application.anki_authentication import AuthenticateAnki
from ankibot.infra.anki.authenticator import AnkiWebAuthenticator
from ankibot.infra.logger import configure_root_logger
from ankibot.presentation.commands import set_commands
from ankibot.presentation.handlers import authenticate, errors, start

from .config import load_config

logger = logging.getLogger(__name__)

_CONFIG_PATH_ENV = "CONFIG_PATH"


async def main() -> None:
    config_path = os.environ.get(_CONFIG_PATH_ENV)
    if config_path is None:
        msg = f"'{_CONFIG_PATH_ENV}' must point at the bot's YAML config"
        raise RuntimeError(msg)

    config = load_config(config_path)

    configure_root_logger(config.logger)

    dp = Dispatcher()
    bot = Bot(token=config.bot.token)

    dp.include_router(start.router)
    dp.include_router(authenticate.router)
    dp.include_router(errors.router)

    http_client = httpx.AsyncClient(timeout=15.0)
    dp.shutdown.register(http_client.aclose)

    authenticate_anki = AuthenticateAnki(
        AnkiWebAuthenticator(config.anki_web, http_client),
    )
    dp["authenticate_anki"] = authenticate_anki

    await set_commands(bot)

    logger.info("Bot has started")

    await dp.start_polling(bot)
