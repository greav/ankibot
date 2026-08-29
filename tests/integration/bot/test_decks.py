"""The /decks outcomes, driven through the composed dispatcher rather than by calling handlers.

Going through ``feed_update`` covers the ``Command("decks")`` filter, the callback-data filters,
router order and aiogram's injection by parameter name on top of the handler bodies.
"""

import logging

import pytest
from aiogram import Dispatcher
from aiogram.methods import EditMessageText, SendMessage
from aiogram.types import InlineKeyboardMarkup, Update

from ankibot.application.exceptions.anki import AnkiDeckListingError, AnkiSessionExpiredError
from ankibot.application.manage_decks import Deck
from ankibot.presentation.keyboards.decks import DeckCallback, DeckPageCallback
from tests.common.fakes.deck_gateway import FakeDeckGateway
from tests.common.fakes.selected_deck_store import FakeSelectedDeckStore
from tests.common.telegram import RecordingSession, make_bot, make_callback_query, make_message

USER_ID = 11
CHAT_ID = 11


async def send(dispatcher: Dispatcher, session: RecordingSession, text: str) -> None:
    """Feed one message to the dispatcher, replies landing in ``session``."""
    bot = make_bot(session)
    update = Update(update_id=1, message=make_message(bot, text=text, chat_id=CHAT_ID, user_id=USER_ID))
    await dispatcher.feed_update(bot, update)


async def tap(dispatcher: Dispatcher, session: RecordingSession, data: str) -> None:
    """Feed one inline-button tap to the dispatcher, replies landing in ``session``."""
    bot = make_bot(session)
    callback = make_callback_query(bot, data, chat_id=CHAT_ID, user_id=USER_ID)
    await dispatcher.feed_update(bot, Update(update_id=2, callback_query=callback))


def button_labels(session: RecordingSession) -> list[str]:
    """The text of every button on the keyboard the bot last sent."""
    message = next(request for request in reversed(session.requests) if isinstance(request, SendMessage))
    assert isinstance(message.reply_markup, InlineKeyboardMarkup)
    return [button.text for row in message.reply_markup.inline_keyboard for button in row]


async def test_user_can_see_their_decks(dispatcher: Dispatcher, selected_decks: FakeSelectedDeckStore) -> None:
    """/decks offers one button per deck, marking the one the user already picked."""
    # Arrange
    selected_decks.decks[USER_ID] = 2
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")

    # Assert
    assert session.last_answer == "Choose a deck:"
    assert button_labels(session) == ["Default", "✓ Spanish"]


async def test_user_can_see_that_they_have_no_decks(dispatcher: Dispatcher, deck_gateway: FakeDeckGateway) -> None:
    """An account with no decks gets told so, not an empty keyboard."""
    # Arrange
    deck_gateway.decks = []
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")

    # Assert
    assert session.last_answer == "You have no decks in AnkiWeb yet."


async def test_user_can_select_a_deck(dispatcher: Dispatcher, selected_decks: FakeSelectedDeckStore) -> None:
    """Tapping a deck confirms it by name and remembers it for the user's next card."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, DeckCallback(id=2).pack())

    # Assert
    assert session.last_edit == "Deck set to Spanish."
    assert selected_decks.decks[USER_ID] == 2


async def test_user_can_page_through_a_long_deck_list(dispatcher: Dispatcher, deck_gateway: FakeDeckGateway) -> None:
    """A list longer than one page pages forward to the decks the first page could not show."""
    # Arrange
    deck_gateway.decks = [Deck(id=index, name=f"deck-{index}") for index in range(20)]
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, DeckPageCallback(page=1).pack())

    # Assert
    edit = next(request for request in reversed(session.requests) if isinstance(request, EditMessageText))
    assert isinstance(edit.reply_markup, InlineKeyboardMarkup)
    labels = [button.text for row in edit.reply_markup.inline_keyboard for button in row]
    assert labels[:8] == [f"deck-{index}" for index in range(8, 16)]


async def test_user_cannot_see_decks_without_authenticating(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway
) -> None:
    """A session-expired failure tells the user to authenticate, not a generic error."""
    # Arrange
    deck_gateway.error = AnkiSessionExpiredError()
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")

    # Assert
    assert session.last_answer == "Run /auth first."


async def test_user_cannot_see_decks_when_ankiweb_fails(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway, caplog: pytest.LogCaptureFixture
) -> None:
    """Any other AnkiWeb failure produces the generic retry message, with the reason only in the log."""
    # Arrange
    deck_gateway.error = AnkiDeckListingError("distinctive-boom-reason")
    session = RecordingSession()

    # Act
    with caplog.at_level(logging.WARNING):
        await send(dispatcher, session, "/decks")

    # Assert
    assert session.last_answer == "Failed to reach AnkiWeb. Please try again later."
    assert "distinctive-boom-reason" in caplog.text


async def test_user_cannot_select_a_deck_that_no_longer_exists(
    dispatcher: Dispatcher, selected_decks: FakeSelectedDeckStore
) -> None:
    """A deck deleted since the keyboard was rendered is refused instead of silently remembered."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, DeckCallback(id=999).pack())

    # Assert
    assert session.last_edit == "That deck no longer exists in AnkiWeb. Run /decks again."
    assert USER_ID not in selected_decks.decks
