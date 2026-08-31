from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka

from ankibot.application.exceptions.base import ApplicationError
from ankibot.application.manage_decks import ListDecks, ListDecksRequest, SelectDeck
from ankibot.presentation.deck_picker import (
    CHOOSE_A_DECK,
    NO_DECKS,
    deck_list_error_reply,
    edit_into,
    select_tapped_deck,
)
from ankibot.presentation.identity import TelegramUserId
from ankibot.presentation.keyboards.decks import DeckCallback, DeckPageCallback, deck_keyboard, page_of

router = Router()


@router.message(Command("decks"))
async def decks_cmd_handler(
    message: Message,
    list_decks: FromDishka[ListDecks],
    user_id: FromDishka[TelegramUserId],
) -> None:
    try:
        result = await list_decks.execute(ListDecksRequest(user_id=user_id))
    except ApplicationError as error:
        await message.answer(deck_list_error_reply(error))
        return

    if not result.decks:
        await message.answer(NO_DECKS)
        return

    keyboard = deck_keyboard(page_of(result.decks, 0), result.selected_deck_id)
    await message.answer(CHOOSE_A_DECK, reply_markup=keyboard)


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
        keyboard = deck_keyboard(page_of(result.decks, callback_data.page), result.selected_deck_id)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(CHOOSE_A_DECK, reply_markup=keyboard)

    await callback.answer()


@router.callback_query(DeckCallback.filter())
async def deck_selected_handler(
    callback: CallbackQuery,
    callback_data: DeckCallback,
    select_deck: FromDishka[SelectDeck],
    user_id: FromDishka[TelegramUserId],
) -> None:
    await select_tapped_deck(callback, user_id, callback_data.id, select_deck, lambda name: f"Deck set to {name}.")
