import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka

from ankibot.application.exceptions.anki import AnkiDeckNotFoundError, AnkiSessionExpiredError
from ankibot.application.exceptions.base import ApplicationError
from ankibot.application.exceptions.decks import BlankDeckNameError, DeckAlreadyExistsError
from ankibot.application.manage_decks import (
    CreateDeck,
    CreateDeckRequest,
    Deck,
    ListDecks,
    ListDecksRequest,
    RemoveDeck,
    RemoveDeckRequest,
    SelectDeck,
)
from ankibot.presentation.deck_picker import (
    AUTH_FIRST,
    CHOOSE_A_DECK,
    CHOOSE_A_DECK_TO_DELETE,
    DECK_CREATION_FAILED,
    DECK_GONE,
    DECK_NAME_BLANK,
    DECK_REMOVAL_FAILED,
    NO_DECKS,
    SEND_DECK_NAME,
    deck_list_error_reply,
    deck_named,
    edit_into,
    select_tapped_deck,
)
from ankibot.presentation.identity import TelegramUserId
from ankibot.presentation.keyboards.decks import (
    ConfirmRemoveDeckCallback,
    DeckCallback,
    DeckPageCallback,
    NewDeckCallback,
    PickerMode,
    RemoveDeckCallback,
    deck_keyboard,
    page_of,
    remove_deck_confirmation_keyboard,
)

logger = logging.getLogger(__name__)

router = Router()


class ManageDecks(StatesGroup):
    waiting_for_deck_name = State()


def picker_text(decks: list[Deck], mode: PickerMode) -> str:
    """The line above the picker: what a tap does in this mode, or that there is nothing to tap."""
    if not decks:
        return NO_DECKS
    return CHOOSE_A_DECK_TO_DELETE if mode is PickerMode.DELETE else CHOOSE_A_DECK


def typed_deck_name(text: str | None) -> str | None:
    """The message as a deck name, or None when it cannot be one.

    A message starting with "/" is a mistyped command, not a name: without this, /word sent while
    the bot waits for a name would create a deck called "/word".
    """
    if text is None or text.lstrip().startswith("/"):
        return None
    return text


@router.message(Command("decks"))
async def decks_cmd_handler(
    message: Message,
    state: FSMContext,
    list_decks: FromDishka[ListDecks],
    user_id: FromDishka[TelegramUserId],
) -> None:
    # Reopening the picker abandons a pending "new deck" prompt; any other flow's state is left
    # alone, since /addcard opens this same picker as one of its own steps.
    if await state.get_state() == ManageDecks.waiting_for_deck_name.state:
        await state.clear()

    try:
        result = await list_decks.execute(ListDecksRequest(user_id=user_id))
    except ApplicationError as error:
        await message.answer(deck_list_error_reply(error))
        return

    keyboard = deck_keyboard(page_of(result.decks, 0), result.selected_deck_id, PickerMode.MANAGE)
    await message.answer(picker_text(result.decks, PickerMode.MANAGE), reply_markup=keyboard)


@router.callback_query(DeckPageCallback.filter())
async def deck_page_handler(
    callback: CallbackQuery,
    callback_data: DeckPageCallback,
    list_decks: FromDishka[ListDecks],
    user_id: FromDishka[TelegramUserId],
) -> None:
    try:
        result = await list_decks.execute(ListDecksRequest(user_id=user_id))
    except ApplicationError as error:
        await edit_into(callback, deck_list_error_reply(error))
    else:
        keyboard = deck_keyboard(
            page_of(result.decks, callback_data.page), result.selected_deck_id, callback_data.mode
        )
        if isinstance(callback.message, Message):
            await callback.message.edit_text(picker_text(result.decks, callback_data.mode), reply_markup=keyboard)

    await callback.answer()


@router.callback_query(DeckCallback.filter())
async def deck_selected_handler(
    callback: CallbackQuery,
    callback_data: DeckCallback,
    select_deck: FromDishka[SelectDeck],
    user_id: FromDishka[TelegramUserId],
) -> None:
    await select_tapped_deck(callback, user_id, callback_data.id, select_deck, lambda name: f"Deck set to {name}.")


@router.callback_query(NewDeckCallback.filter())
async def new_deck_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ManageDecks.waiting_for_deck_name)
    await edit_into(callback, SEND_DECK_NAME)
    await callback.answer()


@router.message(ManageDecks.waiting_for_deck_name)
async def deck_name_handler(
    message: Message,
    state: FSMContext,
    create_deck: FromDishka[CreateDeck],
    user_id: FromDishka[TelegramUserId],
) -> None:
    name = typed_deck_name(message.text)
    if name is None:
        await message.answer(DECK_NAME_BLANK)
        return

    try:
        result = await create_deck.execute(CreateDeckRequest(user_id=user_id, name=name))
    except BlankDeckNameError:
        await message.answer(DECK_NAME_BLANK)
        return  # Still waiting: the user only has to type the name again.
    except DeckAlreadyExistsError as error:
        await message.answer(f"You already have a deck named {error.deck_name}.")
    except AnkiSessionExpiredError:
        await message.answer(AUTH_FIRST)
    except ApplicationError as error:
        logger.warning("Failed to create an AnkiWeb deck: %s", error)
        await message.answer(DECK_CREATION_FAILED)
    else:
        await message.answer(f"Deck {result.deck_name} created. New cards go there now.")

    await state.clear()


@router.callback_query(RemoveDeckCallback.filter())
async def remove_deck_handler(
    callback: CallbackQuery,
    callback_data: RemoveDeckCallback,
    list_decks: FromDishka[ListDecks],
    user_id: FromDishka[TelegramUserId],
) -> None:
    try:
        result = await list_decks.execute(ListDecksRequest(user_id=user_id))
    except ApplicationError as error:
        await edit_into(callback, deck_list_error_reply(error))
    else:
        deck_name = deck_named(result.decks, callback_data.id)
        if deck_name is None:
            await edit_into(callback, DECK_GONE)
        elif isinstance(callback.message, Message):
            await callback.message.edit_text(
                f"Delete {deck_name} and every card in it?",
                reply_markup=remove_deck_confirmation_keyboard(callback_data.id, callback_data.page),
            )

    await callback.answer()


@router.callback_query(ConfirmRemoveDeckCallback.filter())
async def remove_deck_confirmed_handler(
    callback: CallbackQuery,
    callback_data: ConfirmRemoveDeckCallback,
    remove_deck: FromDishka[RemoveDeck],
    user_id: FromDishka[TelegramUserId],
) -> None:
    try:
        result = await remove_deck.execute(RemoveDeckRequest(user_id=user_id, deck_id=callback_data.id))
    except AnkiSessionExpiredError:
        await edit_into(callback, AUTH_FIRST)
    except AnkiDeckNotFoundError:
        await edit_into(callback, DECK_GONE)
    except ApplicationError as error:
        logger.warning("Failed to delete an AnkiWeb deck: %s", error)
        await edit_into(callback, DECK_REMOVAL_FAILED)
    else:
        reply = f"Deck {result.deck_name} deleted."
        if result.was_target:
            reply += " Choose where new cards go with /decks."
        await edit_into(callback, reply)

    await callback.answer()
