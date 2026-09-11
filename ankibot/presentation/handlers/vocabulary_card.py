"""The word → generated card dialog.

A word enters two ways: implicitly — plain text short enough to read as a lookup — and explicitly
through /word, whose waiting state takes text of any length. The generated card is confirmed under
one Save/Regenerate/Cancel keyboard on the preview message.
"""

import contextlib
import logging
from collections.abc import Sequence

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka

from ankibot.application.add_vocabulary_word import GenerateCard, GenerateCardRequest, SaveCard, SaveCardRequest
from ankibot.application.exceptions.anki import AnkiSessionExpiredError, AnkiTemplateTargetNotFoundError
from ankibot.application.exceptions.base import ApplicationError
from ankibot.application.exceptions.generation import CardGenerationError, CardGenerationUnavailableError
from ankibot.presentation.deck_picker import AUTH_FIRST, edit_into
from ankibot.presentation.keyboards.generated_card import GeneratedCardCallback, generated_card_keyboard
from ankibot.presentation.message_kinds import plain_text, word_query

logger = logging.getLogger(__name__)

router = Router()

SEND_A_WORD = "Send a word to make a card from."
NOT_A_WORD = "That doesn't look like a word. Send a word to make a card from."
GENERATOR_UNAVAILABLE = "The card generator is unavailable. Please try again later."
GENERATION_FAILED = "Couldn't generate a card for that word. Try again, or rephrase it."
GENERIC_FAILURE = "Failed to add the card to AnkiWeb. Please try again later."
CANCELLED = "Cancelled."


class WordCard(StatesGroup):
    waiting_for_word = State()
    confirming = State()


def format_card_preview(deck_name: str, fields: Sequence[tuple[str, str]]) -> str:
    """Render the generated card as the preview the user confirms."""
    lines = "\n".join(f"{name}: {value}" for name, value in fields)
    return f"Add to {deck_name}?\n\n{lines}"


async def _clear_previous_keyboard(message: Message, state: FSMContext) -> None:
    """Best-effort strip the keyboard off a pending preview a new word is about to replace."""
    data = await state.get_data()
    preview_message_id = data.get("preview_message_id")
    bot = message.bot
    if preview_message_id is None or bot is None:
        return
    with contextlib.suppress(TelegramBadRequest):
        await bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=preview_message_id, reply_markup=None)


async def _send_preview(message: Message, state: FSMContext, generate_card: GenerateCard, word: str) -> None:
    """Generate a card for ``word`` and reply with its preview, or with the failure that stopped it."""
    bot = message.bot
    if bot is not None:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        result = await generate_card.execute(GenerateCardRequest(word=word))
    except CardGenerationUnavailableError:
        await state.clear()
        await message.answer(GENERATOR_UNAVAILABLE)
        return
    except CardGenerationError:
        await state.clear()
        await message.answer(GENERATION_FAILED)
        return
    except AnkiSessionExpiredError:
        await state.clear()
        await message.answer(AUTH_FIRST)
        return
    except AnkiTemplateTargetNotFoundError as error:
        await state.clear()
        await message.answer(str(error))
        return
    except ApplicationError as error:
        logger.warning("Failed to generate a vocabulary card: %s", error)
        await state.clear()
        await message.answer(GENERIC_FAILURE)
        return

    preview = await message.answer(
        format_card_preview(result.deck_name, list(result.fields)),
        reply_markup=generated_card_keyboard(),
    )
    await state.set_state(WordCard.confirming)
    await state.update_data(word=word, values=dict(result.fields), preview_message_id=preview.message_id)


@router.message(Command("word"))
async def word_cmd_handler(message: Message, state: FSMContext) -> None:
    await _clear_previous_keyboard(message, state)
    await state.set_state(WordCard.waiting_for_word)
    await message.answer(SEND_A_WORD)


@router.message(WordCard.waiting_for_word, F.text, ~F.text.startswith("/"))
async def awaited_word_handler(message: Message, state: FSMContext, generate_card: FromDishka[GenerateCard]) -> None:
    # /word has been sent, so any usable length qualifies — the length line only splits implicit input.
    word = plain_text(message.text)
    if word is None:
        await message.answer(NOT_A_WORD)
        return
    await _send_preview(message, state, generate_card, word)


@router.message(StateFilter(None, WordCard.confirming), F.text, ~F.text.startswith("/"))
async def word_handler(message: Message, state: FSMContext, generate_card: FromDishka[GenerateCard]) -> None:
    word = word_query(message.text)
    if word is None:
        return

    await _clear_previous_keyboard(message, state)
    await _send_preview(message, state, generate_card, word)


@router.callback_query(GeneratedCardCallback.filter(), WordCard.confirming)
async def generated_card_action_handler(
    callback: CallbackQuery,
    callback_data: GeneratedCardCallback,
    state: FSMContext,
    generate_card: FromDishka[GenerateCard],
    save_card: FromDishka[SaveCard],
) -> None:
    if callback_data.action == "cancel":
        await state.clear()
        await edit_into(callback, CANCELLED)
    elif callback_data.action == "regenerate":
        data = await state.get_data()
        word: str = data["word"]
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)
            await _send_preview(callback.message, state, generate_card, word)
    else:
        data = await state.get_data()
        values: dict[str, str] = data["values"]
        try:
            result = await save_card.execute(SaveCardRequest(values=values))
        except AnkiSessionExpiredError:
            await state.clear()
            await edit_into(callback, AUTH_FIRST)
        except AnkiTemplateTargetNotFoundError as error:
            await state.clear()
            await edit_into(callback, str(error))
        except CardGenerationError:
            await state.clear()
            await edit_into(callback, GENERATION_FAILED)
        except ApplicationError as error:
            logger.warning("Failed to save the vocabulary card to AnkiWeb: %s", error)
            await state.clear()
            await edit_into(callback, GENERIC_FAILURE)
        else:
            await state.clear()
            await edit_into(callback, f"Added to {result.deck_name}.")

    await callback.answer()
