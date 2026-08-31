import logging
import os

from aiogram import Bot, Dispatcher
from dishka import AsyncContainer
from dishka.integrations.aiogram import inject_router, setup_dishka

from ankibot.bootstrap.di import make_container, warm_up
from ankibot.infra.logger import configure_root_logger
from ankibot.presentation.commands import set_commands
from ankibot.presentation.handlers import add_card, authenticate, decks, errors, start, vocabulary_card

from .config import load_config

logger = logging.getLogger(__name__)

_CONFIG_PATH_ENV = "CONFIG_PATH"


def create_dispatcher(container: AsyncContainer) -> Dispatcher:
    """Compose the dispatcher: routers in resolution order, over the container behind ``FromDishka``."""
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(authenticate.router)
    # add_card's deck callback is state-filtered, so it wins while the user is mid-/addcard and
    # every other deck callback falls through to decks.router.
    dp.include_router(add_card.router)
    dp.include_router(decks.router)
    # vocabulary_card's catch-all message handler must come after every command-specific router,
    # or it would swallow /decks paging callbacks and any future command's plain-text steps.
    dp.include_router(vocabulary_card.router)
    dp.include_router(errors.router)

    setup_dishka(container=container, router=dp)
    # Injection is applied here rather than through ``setup_dishka(auto_inject=True)``: that variant
    # defers it to ``dp.emit_startup``, which ``feed_update`` never reaches, so every handler test
    # would run against handlers whose ``FromDishka`` arguments are still unfilled. Doing it eagerly
    # also keeps it impossible to forget a per-handler ``@inject``.
    inject_router(dp)

    return dp


async def main() -> None:
    config_path = os.environ.get(_CONFIG_PATH_ENV)
    if config_path is None:
        msg = f"'{_CONFIG_PATH_ENV}' must point at the bot's YAML config"
        raise RuntimeError(msg)

    config = load_config(config_path)

    configure_root_logger(config.logger)

    bot = Bot(token=config.bot.token)

    container = make_container(config)
    try:
        await warm_up(container)
    except Exception:
        await container.close()
        raise

    dp = create_dispatcher(container)
    # Closing the container finalizes every factory that yielded, so the HTTP and SDK clients go
    # down with it; no adapter needs its own shutdown hook.
    dp.shutdown.register(container.close)

    await set_commands(bot)

    logger.info("Bot has started")

    await dp.start_polling(bot)
