"""The word → generated card dialog.

A word enters three ways: implicitly — plain text short enough to read as a lookup — explicitly
through /word, whose waiting state takes text of any length, and after /word as a screenshot of the
text it appears in. A captioned screenshot names its word in the caption; an uncaptioned one gets a
picker of the words worth looking up in it, over which the word can also be typed. Either way the
screenshot goes along as context, so the card quotes the sentence the learner actually met.

The generated card is confirmed under one keyboard on the preview message: Save / Cancel,
Regenerate, and "Regenerate with feedback", which asks what to change first. The keyboard stays
live while the note is awaited, so any of its buttons is the way out of that question.
"""

import contextlib
import logging
from collections.abc import Sequence

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka

from ankibot.application.add_vocabulary_word import (
    CardFeedback,
    GenerateCard,
    GenerateCardRequest,
    SaveCard,
    SaveCardRequest,
    SuggestWords,
    SuggestWordsRequest,
)
from ankibot.application.common.dto.image import Image
from ankibot.application.exceptions.anki import AnkiSessionExpiredError, AnkiTemplateTargetNotFoundError
from ankibot.application.exceptions.base import ApplicationError
from ankibot.application.exceptions.generation import (
    CardGenerationEmptyError,
    CardGenerationError,
    CardGenerationUnavailableError,
)
from ankibot.presentation.deck_picker import AUTH_FIRST, edit_into
from ankibot.presentation.identity import TelegramUserId
from ankibot.presentation.images import PHOTO_JPEG_MIME, download_image
from ankibot.presentation.keyboards.generated_card import GeneratedCardCallback, generated_card_keyboard
from ankibot.presentation.keyboards.word_candidates import WordCandidateCallback, word_candidates_keyboard
from ankibot.presentation.message_kinds import plain_text, word_query

logger = logging.getLogger(__name__)

router = Router()

SEND_A_WORD = "Send a word to make a card from, or a screenshot of the text it appears in."
NOT_A_WORD = "That doesn't look like a word. Send a word to make a card from."
IMAGE_UNREADABLE = "Couldn't read that image. Please try again."
WHICH_WORD = "Which word?"
NO_WORDS_FOUND = (
    "Couldn't find a word worth a card in that screenshot. Send the word as a caption, or another screenshot."
)
GENERATOR_UNAVAILABLE = "The card generator is unavailable. Please try again later."
GENERATION_FAILED = "Couldn't generate a card for that word. Try again, or rephrase it."
GENERIC_FAILURE = "Failed to add the card to AnkiWeb. Please try again later."
ASK_FEEDBACK = "What should change in the regenerated card? Send a note, or use the buttons above."
NOT_FEEDBACK = "That doesn't look like a note. Say what should change, or use the buttons above."
CANCELLED = "Cancelled."


class WordCard(StatesGroup):
    waiting_for_word = State()
    choosing_word = State()
    confirming = State()
    waiting_for_feedback = State()


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


type ScreenshotContext = tuple[Image, str, str]
"""The screenshot a word was met in, with the ``file_id`` and MIME type to fetch it again."""


async def _context_of(bot: Bot | None, data: dict[str, object]) -> ScreenshotContext | None:
    """Re-download the screenshot FSM data points at, or None when the card came from a typed word.

    Raises ``LookupError`` when there was a screenshot but Telegram no longer hands it back.
    """
    file_id = data.get("file_id")
    mime_type = data.get("mime_type")
    if not isinstance(file_id, str) or not isinstance(mime_type, str):
        return None
    image = await download_image(bot, file_id, mime_type) if bot is not None else None
    if image is None:
        raise LookupError(file_id)
    return image, file_id, mime_type


async def _send_preview(
    message: Message,
    state: FSMContext,
    generate_card: GenerateCard,
    user_id: TelegramUserId,
    word: str,
    context: ScreenshotContext | None = None,
    feedback: CardFeedback | None = None,
) -> None:
    """Generate a card for ``word`` and reply with its preview, or with the failure that stopped it.

    ``context`` is the screenshot the word was met in, with the ``file_id`` and MIME type to fetch
    it again for a redo; ``feedback`` is the learner's note on the card shown before.
    """
    bot = message.bot
    if bot is not None:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    image, file_id, mime_type = context if context is not None else (None, None, None)
    try:
        result = await generate_card.execute(
            GenerateCardRequest(user_id=user_id, word=word, context=image, feedback=feedback)
        )
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
    await state.update_data(
        word=word,
        values=dict(result.fields),
        preview_message_id=preview.message_id,
        file_id=file_id,
        mime_type=mime_type,
    )


async def _handle_word_image(
    message: Message,
    state: FSMContext,
    suggest_words: SuggestWords,
    generate_card: GenerateCard,
    user_id: TelegramUserId,
    *,
    file_id: str,
    mime_type: str,
) -> None:
    """A screenshot after /word: its caption names the word, or the learner picks one out of it."""
    bot = message.bot
    if bot is None:
        return
    image = await download_image(bot, file_id, mime_type)
    if image is None:
        await state.clear()
        await message.answer(IMAGE_UNREADABLE)
        return

    word = plain_text(message.caption)
    if word is not None:
        await _send_preview(message, state, generate_card, user_id, word, (image, file_id, mime_type))
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        result = await suggest_words.execute(SuggestWordsRequest(user_id=user_id, image=image))
    except CardGenerationEmptyError:
        await state.set_state(WordCard.waiting_for_word)
        await message.answer(NO_WORDS_FOUND)
        return
    except CardGenerationUnavailableError:
        await state.clear()
        await message.answer(GENERATOR_UNAVAILABLE)
        return
    except CardGenerationError:
        await state.clear()
        await message.answer(GENERATION_FAILED)
        return

    await state.set_state(WordCard.choosing_word)
    await state.update_data(candidates=list(result.words), file_id=file_id, mime_type=mime_type)
    await message.answer(WHICH_WORD, reply_markup=word_candidates_keyboard(result.words))


@router.message(Command("word"))
async def word_cmd_handler(message: Message, state: FSMContext) -> None:
    await _clear_previous_keyboard(message, state)
    await state.set_state(WordCard.waiting_for_word)
    await message.answer(SEND_A_WORD)


@router.message(StateFilter(WordCard.waiting_for_word, WordCard.choosing_word), F.text, ~F.text.startswith("/"))
async def awaited_word_handler(
    message: Message,
    state: FSMContext,
    generate_card: FromDishka[GenerateCard],
    user_id: FromDishka[TelegramUserId],
) -> None:
    # /word has been sent, so any usable length qualifies — the length line only splits implicit input.
    word = plain_text(message.text)
    if word is None:
        await message.answer(NOT_A_WORD)
        return
    # Typed over the picker, the word the model missed still gets the screenshot as its context.
    context = None
    if await state.get_state() == WordCard.choosing_word:
        try:
            context = await _context_of(message.bot, await state.get_data())
        except LookupError:
            await state.clear()
            await message.answer(IMAGE_UNREADABLE)
            return
    await _send_preview(message, state, generate_card, user_id, word, context)


@router.message(StateFilter(WordCard.waiting_for_word, WordCard.choosing_word), F.photo)
async def word_photo_handler(
    message: Message,
    state: FSMContext,
    suggest_words: FromDishka[SuggestWords],
    generate_card: FromDishka[GenerateCard],
    user_id: FromDishka[TelegramUserId],
) -> None:
    if not message.photo:
        return
    # The last PhotoSize is the largest one Telegram offers.
    file_id = message.photo[-1].file_id
    await _handle_word_image(
        message, state, suggest_words, generate_card, user_id, file_id=file_id, mime_type=PHOTO_JPEG_MIME
    )


@router.message(
    StateFilter(WordCard.waiting_for_word, WordCard.choosing_word),
    F.document.mime_type.startswith("image/"),
)
async def word_document_handler(
    message: Message,
    state: FSMContext,
    suggest_words: FromDishka[SuggestWords],
    generate_card: FromDishka[GenerateCard],
    user_id: FromDishka[TelegramUserId],
) -> None:
    document = message.document
    if document is None or document.mime_type is None:
        return
    await _handle_word_image(
        message,
        state,
        suggest_words,
        generate_card,
        user_id,
        file_id=document.file_id,
        mime_type=document.mime_type,
    )


@router.callback_query(WordCandidateCallback.filter(), WordCard.choosing_word)
async def word_candidate_handler(
    callback: CallbackQuery,
    callback_data: WordCandidateCallback,
    state: FSMContext,
    generate_card: FromDishka[GenerateCard],
    user_id: FromDishka[TelegramUserId],
) -> None:
    """The learner picked a word off the screenshot: make its card with the screenshot as context."""
    data = await state.get_data()
    candidates: list[str] = data.get("candidates", [])
    if isinstance(callback.message, Message) and 0 <= callback_data.index < len(candidates):
        message = callback.message
        word = candidates[callback_data.index]
        await message.edit_reply_markup(reply_markup=None)
        try:
            context = await _context_of(message.bot, data)
        except LookupError:
            await state.clear()
            await message.answer(IMAGE_UNREADABLE)
        else:
            await _send_preview(message, state, generate_card, user_id, word, context)
    await callback.answer()


@router.message(StateFilter(None, WordCard.confirming), F.text, ~F.text.startswith("/"))
async def word_handler(
    message: Message,
    state: FSMContext,
    generate_card: FromDishka[GenerateCard],
    user_id: FromDishka[TelegramUserId],
) -> None:
    word = word_query(message.text)
    if word is None:
        return

    await _clear_previous_keyboard(message, state)
    await _send_preview(message, state, generate_card, user_id, word)


@router.message(WordCard.waiting_for_feedback, F.text, ~F.text.startswith("/"))
async def feedback_text_handler(
    message: Message,
    state: FSMContext,
    generate_card: FromDishka[GenerateCard],
    user_id: FromDishka[TelegramUserId],
) -> None:
    """The note "Regenerate with feedback" asked for: redo the card with it."""
    note = plain_text(message.text)
    if note is None:
        await message.answer(NOT_FEEDBACK)
        return
    data = await state.get_data()
    word: str = data["word"]
    previous: dict[str, str] = data["values"]
    try:
        context = await _context_of(message.bot, data)
    except LookupError:
        await state.clear()
        await message.answer(IMAGE_UNREADABLE)
        return
    await _clear_previous_keyboard(message, state)
    await _send_preview(
        message, state, generate_card, user_id, word, context, CardFeedback(note=note, previous=previous)
    )


@router.callback_query(GeneratedCardCallback.filter(), StateFilter(WordCard.confirming, WordCard.waiting_for_feedback))
async def generated_card_action_handler(
    callback: CallbackQuery,
    callback_data: GeneratedCardCallback,
    state: FSMContext,
    generate_card: FromDishka[GenerateCard],
    save_card: FromDishka[SaveCard],
    user_id: FromDishka[TelegramUserId],
) -> None:
    if callback_data.action == "cancel":
        await state.clear()
        await edit_into(callback, CANCELLED)
    elif callback_data.action == "regenerate":
        data = await state.get_data()
        word: str = data["word"]
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)
            try:
                context = await _context_of(callback.message.bot, data)
            except LookupError:
                await state.clear()
                await edit_into(callback, IMAGE_UNREADABLE)
            else:
                await _send_preview(callback.message, state, generate_card, user_id, word, context)
    elif callback_data.action == "feedback":
        if isinstance(callback.message, Message):
            await state.set_state(WordCard.waiting_for_feedback)
            await callback.message.answer(ASK_FEEDBACK)
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
