import logging
import os

from aiogram import Bot, Dispatcher

from ankibot.application.english_card_generation import GenerateEnglishCardInteractor
from ankibot.infra.ai.openai_card_generator import OpenAICardGenerator
from ankibot.infra.anki.httpx_anki_gateway import HttpxAnkiWebGateway
from ankibot.infra.logger import configure_root_logger
from ankibot.presentation.handlers import english_card_generation, start

from .config import load_config

logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config(os.getenv("CONFIG_PATH", "./configs/config.yaml"))

    configure_root_logger(config.logger)

    dp = Dispatcher()
    bot = Bot(token=config.bot.token)

    card_generator = OpenAICardGenerator(config.openai)
    anki_gateway = HttpxAnkiWebGateway(config.ankiweb)
    interactor = GenerateEnglishCardInteractor(
        card_generator=card_generator,
        anki_gateway=anki_gateway,
        template=config.card_template,
    )

    dp.include_router(start.router)
    dp.include_router(english_card_generation.build_router(interactor))

    dp.shutdown.register(anki_gateway.aclose)

    await dp.start_polling(bot)

    logger.info("Bot has started")
