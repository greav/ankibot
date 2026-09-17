"""The snippet → generated cards dialog.

A snippet enters two ways: implicitly — text longer than a word lookup, or an image — and
explicitly through /snippet, whose waiting state takes text of any length. The generated cards sit
under one keyboard on the last preview message: a numbered toggle per card, all selected at first,
and Save / Regenerate / Cancel acting on the selection. Regenerate replaces the unticked cards and
keeps the ticked ones — or, with nothing unticked, replaces the whole batch. "Regenerate with
feedback" does the same after asking what to change; the preview keyboard stays live meanwhile,
so any of its buttons is the way out of that question. "Change deck" sends the /decks picker as
a separate message: the tapped deck is stored exactly as /decks stores it, and the preview's
header is rewritten to name it, so what Save reports is what the header promised.
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
from aiogram.utils.formatting import Bold, Text
from dishka import FromDishka

from ankibot.application.add_snippet_cards import (
    DraftCard,
    GenerateCards,
    GenerateSnippetCardsRequest,
    SaveCards,
    SaveSnippetCardsRequest,
    Snippet,
)
from ankibot.application.exceptions.anki import (
    AnkiDeckNotFoundError,
    AnkiSessionExpiredError,
    AnkiUnsupportedNotetypeError,
    SnippetCardsPartiallySavedError,
)
from ankibot.application.exceptions.base import ApplicationError
from ankibot.application.exceptions.decks import NoDeckSelectedError
from ankibot.application.exceptions.generation import (
    CardGenerationEmptyError,
    CardGenerationError,
    CardGenerationUnavailableError,
)
from ankibot.application.manage_decks import ListDecks, ListDecksRequest, SelectDeck
from ankibot.presentation.deck_picker import (
    AUTH_FIRST,
    CHOOSE_A_DECK,
    CHOOSE_DECK_FIRST,
    DECK_GONE,
    NO_DECKS,
    deck_list_error_reply,
    edit_into,
    select_tapped_deck,
)
from ankibot.presentation.identity import TelegramUserId
from ankibot.presentation.images import PHOTO_JPEG_MIME, download_image
from ankibot.presentation.keyboards.decks import DeckCallback, deck_keyboard, page_of
from ankibot.presentation.keyboards.snippet_cards import SnippetCardCallback, snippet_cards_keyboard, toggled
from ankibot.presentation.message_kinds import plain_text, snippet_text

logger = logging.getLogger(__name__)

router = Router()

TELEGRAM_MESSAGE_LIMIT = 4096

SEND_A_SNIPPET = "Send a text snippet or a screenshot to make cards from."
NOT_A_SNIPPET = "That doesn't look like a snippet. Send a text snippet or a screenshot."
IMAGE_UNREADABLE = "Couldn't read that image. Please try again."
GENERATOR_UNAVAILABLE = "The card generator is unavailable. Please try again later."
GENERATION_FAILED = "Couldn't generate cards from that snippet. Try again, or send a different passage."
NOTHING_TO_LEARN = "Couldn't find anything card-worthy in that snippet. Try a different passage."
UNSUPPORTED_NOTETYPE = (
    "AnkiWeb's current notetype isn't set up for a simple front/back card. "
    "Switch to a two-field notetype (e.g. Basic) in AnkiWeb's editor and try again."
)
GENERIC_FAILURE = "Failed to add the cards to AnkiWeb. Please try again later."
NOTHING_SELECTED = "Select at least one card."
ASK_FEEDBACK = "What should change in the regenerated cards? Send a note, or use the buttons above."
NOT_FEEDBACK = "That doesn't look like a note. Say what should change, or use the buttons above."
CANCELLED = "Cancelled."


class SnippetCards(StatesGroup):
    waiting_for_snippet = State()
    confirming = State()
    waiting_for_feedback = State()
    choosing_deck = State()


def format_cards_preview(deck_name: str, cards: Sequence[DraftCard]) -> list[Text]:
    """Render the generated cards as preview texts, each within Telegram's message limit.

    One message when everything fits; the confirmation keyboard goes on the last one either way,
    its toggles numbered to match the cards listed here. Each card's front is bold, as entities
    rather than markup: the cards are model output, so they may carry anything a parse mode would
    trip over, and entities leave the text itself unparsed.
    """
    count = "1 card" if len(cards) == 1 else f"{len(cards)} cards"
    current = Text(f"Add {count} to ", deck_name, "?")
    messages: list[Text] = []
    for index, card in enumerate(cards, start=1):
        block = Text(Bold(f"{index}. {card.front}"), "\n— ", card.back)[:TELEGRAM_MESSAGE_LIMIT]
        candidate = current + Text("\n\n", block)
        if len(candidate) > TELEGRAM_MESSAGE_LIMIT:
            messages.append(current)
            current = block
        else:
            current = candidate
    messages.append(current)
    return messages


def format_saved(saved: int, deck_name: str) -> str:
    """The confirmation the user gets once the whole batch is in."""
    count = "1 card" if saved == 1 else f"{saved} cards"
    return f"Added {count} to {deck_name}."


def format_partial_save(error: SnippetCardsPartiallySavedError) -> str:
    """The honest reply for a batch AnkiWeb accepted only part of."""
    return (
        f"Saved {error.saved} of {error.total} cards to {error.deck_name}, then AnkiWeb failed. "
        "Resend the snippet to add the rest."
    )


async def _clear_previous_keyboard(message: Message, state: FSMContext) -> None:
    """Best-effort strip the keyboard off a pending preview a new snippet is about to replace."""
    data = await state.get_data()
    preview_message_id = data.get("preview_message_id")
    bot = message.bot
    if preview_message_id is None or bot is None:
        return
    with contextlib.suppress(TelegramBadRequest):
        await bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=preview_message_id, reply_markup=None)


def _source_of(data: dict[str, object]) -> dict[str, str | None]:
    """The snippet's source as ``_send_preview`` stored it, for a regeneration to carry forward."""
    return {
        key: value if isinstance(value := data.get(key), str) else None
        for key in ("text", "file_id", "mime_type", "hint")
    }


async def _restore_snippet(bot: Bot | None, source: dict[str, str | None]) -> Snippet | None:
    """Rebuild the snippet from its stored source — re-downloading an image by its file_id.

    None when the image can no longer be fetched; a text snippet always restores.
    """
    hint = source["hint"]
    text = source["text"]
    if text is not None:
        return Snippet(text=text, hint=hint)
    file_id = source["file_id"]
    mime_type = source["mime_type"]
    if file_id is None or mime_type is None or bot is None:
        return None
    image = await download_image(bot, file_id, mime_type)
    if image is None:
        return None
    return Snippet(image=image, hint=hint)


async def _send_preview(
    message: Message,
    state: FSMContext,
    generate_cards: GenerateCards,
    user_id: TelegramUserId,
    snippet: Snippet,
    source: dict[str, str | None],
    kept: tuple[DraftCard, ...] = (),
    feedback: str | None = None,
) -> None:
    """Generate cards for ``snippet`` and reply with their preview, or with the failure that stopped it.

    ``source`` is what Regenerate rebuilds the snippet from — its text, or its image's ``file_id``
    to re-download; the bytes themselves never enter FSM data. ``kept`` are the cards Regenerate
    carries over from the previous batch, ``feedback`` the learner's note on what to change.
    """
    bot = message.bot
    if bot is not None:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        result = await generate_cards.execute(
            GenerateSnippetCardsRequest(user_id=user_id, snippet=snippet, kept=kept, feedback=feedback)
        )
    except CardGenerationUnavailableError:
        await state.clear()
        await message.answer(GENERATOR_UNAVAILABLE)
        return
    except CardGenerationEmptyError:
        await state.clear()
        await message.answer(NOTHING_TO_LEARN)
        return
    except CardGenerationError:
        await state.clear()
        await message.answer(GENERATION_FAILED)
        return
    except AnkiSessionExpiredError:
        await state.clear()
        await message.answer(AUTH_FIRST)
        return
    except NoDeckSelectedError:
        await state.clear()
        await message.answer(CHOOSE_DECK_FIRST)
        return
    except AnkiDeckNotFoundError:
        await state.clear()
        await message.answer(DECK_GONE)
        return
    except AnkiUnsupportedNotetypeError:
        await state.clear()
        await message.answer(UNSUPPORTED_NOTETYPE)
        return
    except ApplicationError as error:
        logger.warning("Failed to generate snippet cards: %s", error)
        await state.clear()
        await message.answer(GENERIC_FAILURE)
        return

    *head, tail = format_cards_preview(result.deck_name, result.cards)
    # The header names the deck; Change deck rewrites it in place, so its message is tracked
    # separately from the keyboard's — they coincide unless the preview had to be split.
    header_message_id: int | None = None
    for text in head:
        sent = await message.answer(**text.as_kwargs())
        if header_message_id is None:
            header_message_id = sent.message_id
    selected = [True] * len(result.cards)
    preview = await message.answer(**tail.as_kwargs(), reply_markup=snippet_cards_keyboard(selected))
    await state.set_state(SnippetCards.confirming)
    await state.update_data(
        {
            "cards": [{"front": card.front, "back": card.back} for card in result.cards],
            "selected": selected,
            "preview_message_id": preview.message_id,
            "header_message_id": preview.message_id if header_message_id is None else header_message_id,
            **source,
        }
    )


async def _handle_image(
    message: Message,
    state: FSMContext,
    generate_cards: GenerateCards,
    user_id: TelegramUserId,
    *,
    file_id: str,
    mime_type: str,
) -> None:
    """Download the sent image and run it through the preview flow, its caption as the hint."""
    bot = message.bot
    if bot is None:
        return
    await _clear_previous_keyboard(message, state)
    image = await download_image(bot, file_id, mime_type)
    if image is None:
        await state.clear()
        await message.answer(IMAGE_UNREADABLE)
        return
    hint = plain_text(message.caption)
    snippet = Snippet(image=image, hint=hint)
    source: dict[str, str | None] = {"text": None, "file_id": file_id, "mime_type": mime_type, "hint": hint}
    await _send_preview(message, state, generate_cards, user_id, snippet, source)


@router.message(Command("snippet"))
async def snippet_cmd_handler(message: Message, state: FSMContext) -> None:
    await _clear_previous_keyboard(message, state)
    await state.set_state(SnippetCards.waiting_for_snippet)
    await message.answer(SEND_A_SNIPPET)


@router.message(
    StateFilter(None, SnippetCards.confirming, SnippetCards.choosing_deck), F.text.func(snippet_text).as_("snippet")
)
async def snippet_text_handler(
    message: Message,
    snippet: str,
    state: FSMContext,
    generate_cards: FromDishka[GenerateCards],
    user_id: FromDishka[TelegramUserId],
) -> None:
    # The filter claims only what ``snippet_text`` accepts, so a short word falls through to the
    # vocabulary-word router behind this one.
    await _clear_previous_keyboard(message, state)
    source: dict[str, str | None] = {"text": snippet, "file_id": None, "mime_type": None, "hint": None}
    await _send_preview(message, state, generate_cards, user_id, Snippet(text=snippet), source)


@router.message(SnippetCards.waiting_for_snippet, F.text, ~F.text.startswith("/"))
async def awaited_snippet_handler(
    message: Message,
    state: FSMContext,
    generate_cards: FromDishka[GenerateCards],
    user_id: FromDishka[TelegramUserId],
) -> None:
    # /snippet has been sent, so any usable length qualifies — this is the short passage's door.
    # Commands are left to the routers behind, so /word can switch flows from here.
    text = plain_text(message.text)
    if text is None:
        await message.answer(NOT_A_SNIPPET)
        return
    source: dict[str, str | None] = {"text": text, "file_id": None, "mime_type": None, "hint": None}
    await _send_preview(message, state, generate_cards, user_id, Snippet(text=text), source)


@router.message(SnippetCards.waiting_for_feedback, F.text, ~F.text.startswith("/"))
async def feedback_text_handler(
    message: Message,
    state: FSMContext,
    generate_cards: FromDishka[GenerateCards],
    user_id: FromDishka[TelegramUserId],
) -> None:
    """The note "Regenerate with feedback" asked for: regenerate the unticked cards with it."""
    feedback = plain_text(message.text)
    if feedback is None:
        await message.answer(NOT_FEEDBACK)
        return
    data = await state.get_data()
    kept = kept_cards(data.get("cards", []), data.get("selected", []))
    source = _source_of(data)
    snippet = await _restore_snippet(message.bot, source)
    if snippet is None:
        await state.clear()
        await message.answer(IMAGE_UNREADABLE)
        return
    await _clear_previous_keyboard(message, state)
    await _send_preview(message, state, generate_cards, user_id, snippet, source, kept, feedback)


@router.message(
    StateFilter(
        None,
        SnippetCards.waiting_for_snippet,
        SnippetCards.confirming,
        SnippetCards.waiting_for_feedback,
        SnippetCards.choosing_deck,
    ),
    F.photo,
)
async def snippet_photo_handler(
    message: Message,
    state: FSMContext,
    generate_cards: FromDishka[GenerateCards],
    user_id: FromDishka[TelegramUserId],
) -> None:
    if not message.photo:
        return
    # The last PhotoSize is the largest one Telegram offers.
    file_id = message.photo[-1].file_id
    await _handle_image(message, state, generate_cards, user_id, file_id=file_id, mime_type=PHOTO_JPEG_MIME)


@router.message(
    StateFilter(
        None,
        SnippetCards.waiting_for_snippet,
        SnippetCards.confirming,
        SnippetCards.waiting_for_feedback,
        SnippetCards.choosing_deck,
    ),
    F.document.mime_type.startswith("image/"),
)
async def snippet_document_handler(
    message: Message,
    state: FSMContext,
    generate_cards: FromDishka[GenerateCards],
    user_id: FromDishka[TelegramUserId],
) -> None:
    document = message.document
    if document is None or document.mime_type is None:
        return
    await _handle_image(
        message, state, generate_cards, user_id, file_id=document.file_id, mime_type=document.mime_type
    )


@router.callback_query(
    SnippetCardCallback.filter(),
    StateFilter(SnippetCards.confirming, SnippetCards.waiting_for_feedback, SnippetCards.choosing_deck),
)
async def snippet_cards_action_handler(
    callback: CallbackQuery,
    callback_data: SnippetCardCallback,
    state: FSMContext,
    generate_cards: FromDishka[GenerateCards],
    save_cards: FromDishka[SaveCards],
    list_decks: FromDishka[ListDecks],
    user_id: FromDishka[TelegramUserId],
) -> None:
    toast: str | None = None
    if callback_data.action == "cancel":
        await state.clear()
        await edit_into(callback, CANCELLED)
    elif callback_data.action == "regenerate":
        await _regenerate(callback, state, generate_cards, user_id)
    elif callback_data.action == "feedback":
        await _ask_feedback(callback, state)
    elif callback_data.action == "toggle":
        await _toggle(callback, callback_data.index, state)
    elif callback_data.action == "deck":
        toast = await _open_deck_picker(callback, state, list_decks, user_id)
    else:
        toast = await _save(callback, state, save_cards, user_id)

    await callback.answer(toast)


@router.callback_query(DeckCallback.filter(), SnippetCards.choosing_deck)
async def snippet_deck_chosen_handler(
    callback: CallbackQuery,
    callback_data: DeckCallback,
    state: FSMContext,
    select_deck: FromDishka[SelectDeck],
    user_id: FromDishka[TelegramUserId],
) -> None:
    """A deck tapped in the picker Change deck sent: store it and re-address the pending preview.

    The preview stands either way — Save resolves the deck afresh — so the dialog is back to
    confirming even when the tap failed and the picker says why.
    """
    await state.set_state(SnippetCards.confirming)
    deck_name = await select_tapped_deck(
        callback, user_id, callback_data.id, select_deck, lambda name: f"Deck set to {name}."
    )
    if deck_name is not None:
        await _readdress_preview(callback, state, deck_name)


def _is_current_preview(callback: CallbackQuery, data: dict[str, object]) -> bool:
    """Whether the tap landed on the preview FSM data still tracks.

    A superseded preview normally loses its keyboard, but that strip is best-effort: a tap that
    still arrives from it must not resurrect its keyboard or save a batch the user has moved on from.
    """
    return isinstance(callback.message, Message) and callback.message.message_id == data.get("preview_message_id")


async def _open_deck_picker(
    callback: CallbackQuery, state: FSMContext, list_decks: ListDecks, user_id: TelegramUserId
) -> str | None:
    """Send the /decks picker under the preview, or return the toast saying why it could not be shown.

    The preview is left as it is in every case: a deck list that cannot be read is no reason to
    lose a generated batch.
    """
    if not isinstance(callback.message, Message):
        return None
    data = await state.get_data()
    if not _is_current_preview(callback, data):
        return None
    try:
        result = await list_decks.execute(ListDecksRequest(user_id=user_id))
    except ApplicationError as error:
        return deck_list_error_reply(error)
    if not result.decks:
        return NO_DECKS

    keyboard = deck_keyboard(page_of(result.decks, 0), result.selected_deck_id)
    await callback.message.answer(CHOOSE_A_DECK, reply_markup=keyboard)
    await state.set_state(SnippetCards.choosing_deck)
    return None


async def _readdress_preview(callback: CallbackQuery, state: FSMContext, deck_name: str) -> None:
    """Rewrite the preview's header to name ``deck_name``, keeping the keyboard when they share a message.

    Best-effort like the keyboard strip: the deck is already stored and the picker already says
    so, so a header Telegram no longer lets us edit is not worth failing the tap over.
    """
    bot = callback.bot
    if bot is None or not isinstance(callback.message, Message):
        return
    data = await state.get_data()
    header_message_id = data.get("header_message_id")
    if not isinstance(header_message_id, int):
        return
    stored: list[dict[str, str]] = data.get("cards", [])
    cards = [DraftCard(front=item["front"], back=item["back"]) for item in stored]
    header, *_ = format_cards_preview(deck_name, cards)
    keyboard = None
    if header_message_id == data.get("preview_message_id"):
        keyboard = snippet_cards_keyboard(data.get("selected", [True] * len(cards)))
    with contextlib.suppress(TelegramBadRequest):
        await bot.edit_message_text(
            **header.as_kwargs(), chat_id=callback.message.chat.id, message_id=header_message_id, reply_markup=keyboard
        )


async def _toggle(callback: CallbackQuery, index: int, state: FSMContext) -> None:
    """Flip one card in or out of the selection and redraw the keyboard to show it."""
    if not isinstance(callback.message, Message):
        return
    data = await state.get_data()
    if not _is_current_preview(callback, data):
        return
    selected: list[bool] = data.get("selected", [])
    updated = list(toggled(selected, index))
    await state.update_data({"selected": updated})
    await callback.message.edit_reply_markup(reply_markup=snippet_cards_keyboard(updated))


def kept_cards(stored: Sequence[dict[str, str]], selected: Sequence[bool]) -> tuple[DraftCard, ...]:
    """The ticked cards Regenerate carries over — none when nothing is unticked, so it replaces them all."""
    if all(selected):
        return ()
    return tuple(
        DraftCard(front=item["front"], back=item["back"])
        for item, chosen in zip(stored, selected, strict=True)
        if chosen
    )


async def _ask_feedback(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask what to change; the answer arrives as text in the waiting_for_feedback state."""
    if not isinstance(callback.message, Message):
        return
    data = await state.get_data()
    if not _is_current_preview(callback, data):
        return
    await state.set_state(SnippetCards.waiting_for_feedback)
    await callback.message.answer(ASK_FEEDBACK)


async def _regenerate(
    callback: CallbackQuery, state: FSMContext, generate_cards: GenerateCards, user_id: TelegramUserId
) -> None:
    """Rebuild the snippet from FSM data — re-downloading an image by its file_id — and re-preview.

    The ticked cards come along unchanged; only the unticked ones are generated anew.
    """
    if not isinstance(callback.message, Message):
        return
    message = callback.message
    data = await state.get_data()
    if not _is_current_preview(callback, data):
        return
    kept = kept_cards(data.get("cards", []), data.get("selected", []))
    source = _source_of(data)
    snippet = await _restore_snippet(message.bot, source)
    if snippet is None:
        await state.clear()
        await edit_into(callback, IMAGE_UNREADABLE)
        return

    await message.edit_reply_markup(reply_markup=None)
    await _send_preview(message, state, generate_cards, user_id, snippet, source, kept)


async def _save(
    callback: CallbackQuery, state: FSMContext, save_cards: SaveCards, user_id: TelegramUserId
) -> str | None:
    """Save the selected cards, answering with exactly what made it into AnkiWeb.

    Returns the toast to answer the tap with, when there is one: nothing selected leaves the
    preview as it is and says so, instead of editing it away.
    """
    data = await state.get_data()
    if not _is_current_preview(callback, data):
        return None
    stored: list[dict[str, str]] = data.get("cards", [])
    selected: list[bool] = data.get("selected", [True] * len(stored))
    cards = tuple(
        DraftCard(front=item["front"], back=item["back"])
        for item, chosen in zip(stored, selected, strict=True)
        if chosen
    )
    if not cards:
        return NOTHING_SELECTED

    try:
        result = await save_cards.execute(SaveSnippetCardsRequest(user_id=user_id, cards=cards))
    except AnkiSessionExpiredError:
        await state.clear()
        await edit_into(callback, AUTH_FIRST)
    except NoDeckSelectedError:
        await state.clear()
        await edit_into(callback, CHOOSE_DECK_FIRST)
    except AnkiDeckNotFoundError:
        await state.clear()
        await edit_into(callback, DECK_GONE)
    except AnkiUnsupportedNotetypeError:
        await state.clear()
        await edit_into(callback, UNSUPPORTED_NOTETYPE)
    except SnippetCardsPartiallySavedError as error:
        await state.clear()
        await edit_into(callback, format_partial_save(error))
    except ApplicationError as error:
        logger.warning("Failed to save snippet cards to AnkiWeb: %s", error)
        await state.clear()
        await edit_into(callback, GENERIC_FAILURE)
    else:
        await state.clear()
        await edit_into(callback, format_saved(result.saved, result.deck_name))
    return None
