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


def create_dispatcher(authenticate_anki: AuthenticateAnki) -> Dispatcher:
    """Compose the dispatcher: routers in resolution order, plus the dependencies handlers ask for."""
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(authenticate.router)
    dp.include_router(errors.router)

    # aiogram injects handler arguments by parameter name, so this key is a contract with
    # every handler declaring an ``authenticate_anki`` argument.
    dp["authenticate_anki"] = authenticate_anki

    return dp


async def main() -> None:
    config_path = os.environ.get(_CONFIG_PATH_ENV)
    if config_path is None:
        msg = f"'{_CONFIG_PATH_ENV}' must point at the bot's YAML config"
        raise RuntimeError(msg)

    config = load_config(config_path)

    configure_root_logger(config.logger)

    bot = Bot(token=config.bot.token)

    http_client = httpx.AsyncClient(timeout=15.0)
    authenticate_anki = AuthenticateAnki(
        AnkiWebAuthenticator(config.anki_web, http_client),
    )

    dp = create_dispatcher(authenticate_anki)
    dp.shutdown.register(http_client.aclose)

    await set_commands(bot)

    logger.info("Bot has started")

    await dp.start_polling(bot)
