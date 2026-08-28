import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ankibot.application.anki_authentication import AuthenticateAnki
from ankibot.application.exceptions.anki import (
    AnkiInvalidPasswordError,
    AnkiInvalidUsernameError,
)
from ankibot.application.exceptions.base import ApplicationError

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("auth"))
async def authenticate_cmd_handler(message: Message, authenticate_anki: AuthenticateAnki) -> None:
    try:
        await authenticate_anki.execute()
    except AnkiInvalidUsernameError:
        await message.answer("AnkiWeb rejected the configured username.")
    except AnkiInvalidPasswordError:
        await message.answer("AnkiWeb rejected the configured password.")
    except ApplicationError as error:
        logger.warning("Failed to authenticate with AnkiWeb: %s", error)
        await message.answer("Failed to authenticate with AnkiWeb. Please try again later.")
    else:
        await message.answer("Authenticated with AnkiWeb.")
