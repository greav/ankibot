import logging

from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from ankibot.application.exceptions.anki import AnkiSessionExpiredError, AnkiUnsupportedNotetypeError
from ankibot.application.exceptions.base import ApplicationError
from ankibot.application.manage_cards import CreateCard, CreateCardRequest

logger = logging.getLogger(__name__)

router = Router()


class AddCard(StatesGroup):
    waiting_for_front = State()
    waiting_for_back = State()


def card_side(text: str | None) -> str | None:
    """Normalize a message into a card side, or None when it carries no usable text.

    Rejects empty/whitespace-only text and text starting with "/", so a mistyped command does not
    silently become a card side.
    """
    if text is None:
        return None
    stripped = text.strip()
    if not stripped or stripped.startswith("/"):
        return None
    return stripped


@router.message(Command("cancel"), StateFilter("*"))
async def cancel_cmd_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Cancelled.")


@router.message(Command("addcard"))
async def add_card_cmd_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(AddCard.waiting_for_front)
    await message.answer("Send the front side.")


@router.message(AddCard.waiting_for_front)
async def front_handler(message: Message, state: FSMContext) -> None:
    front = card_side(message.text)
    if front is None:
        await message.answer("The front side can't be empty. Send the front side.")
        return

    await state.update_data(front=front)
    await state.set_state(AddCard.waiting_for_back)
    await message.answer("Send the back side.")


@router.message(AddCard.waiting_for_back)
async def back_handler(message: Message, state: FSMContext, create_card: CreateCard) -> None:
    back = card_side(message.text)
    if back is None:
        await message.answer("The back side can't be empty. Send the back side.")
        return

    data = await state.get_data()
    front: str = data["front"]

    try:
        result = await create_card.execute(CreateCardRequest(front=front, back=back))
    except AnkiUnsupportedNotetypeError:
        await state.clear()
        await message.answer(
            "AnkiWeb's current notetype isn't set up for a simple front/back card. "
            "Switch to a two-field notetype (e.g. Basic) in AnkiWeb's editor and try again."
        )
    except AnkiSessionExpiredError:
        await state.clear()
        await message.answer("Run /auth first.")
    except ApplicationError as error:
        logger.warning("Failed to add the card to AnkiWeb: %s", error)
        await state.clear()
        await message.answer("Failed to add the card to AnkiWeb. Please try again later.")
    else:
        await state.clear()
        await message.answer(f"Card added to {result.deck_name}.")
