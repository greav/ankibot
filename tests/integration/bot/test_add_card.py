"""The /addcard dialog outcomes, driven through the composed dispatcher rather than by calling
handlers directly.

Going through ``feed_update`` covers the command filters, router order (``/cancel`` winning inside
a state, and the state-filtered deck callback winning over ``decks.router``) and aiogram's
injection by parameter name on top of the handler bodies.
"""

import asyncio
import logging

import pytest
from aiogram import Dispatcher
from aiogram.types import Update

from ankibot.application.exceptions.anki import (
    AnkiCardCreationError,
    AnkiDeckListingError,
    AnkiSessionExpiredError,
)
from ankibot.presentation.handlers.add_card import AddCard
from ankibot.presentation.keyboards.decks import DeckCallback
from tests.common.fakes.card_gateway import FakeCardGateway
from tests.common.fakes.deck_gateway import FakeDeckGateway
from tests.common.fakes.selected_deck_store import FakeSelectedDeckStore
from tests.common.telegram import RecordingSession, make_bot, make_callback_query, make_message

DEFAULT_DECK_ID = 1
SPANISH_DECK_ID = 2


async def send(dispatcher: Dispatcher, session: RecordingSession, text: str, *, chat_id: int, user_id: int) -> None:
    """Feed one message from (chat_id, user_id) to the dispatcher, replies landing in ``session``."""
    bot = make_bot(session)
    update = Update(update_id=1, message=make_message(bot, text=text, chat_id=chat_id, user_id=user_id))
    await dispatcher.feed_update(bot, update)


async def pick_deck(
    dispatcher: Dispatcher, session: RecordingSession, deck_id: int, *, chat_id: int, user_id: int
) -> None:
    """Tap a deck on the picker /addcard opens with."""
    bot = make_bot(session)
    callback = make_callback_query(bot, DeckCallback(id=deck_id).pack(), chat_id=chat_id, user_id=user_id)
    await dispatcher.feed_update(bot, Update(update_id=2, callback_query=callback))


async def test_user_can_add_a_card(dispatcher: Dispatcher) -> None:
    """A full pick/front/back dialog ends with a reply naming the deck the card landed in."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=1, user_id=1)
    await pick_deck(dispatcher, session, SPANISH_DECK_ID, chat_id=1, user_id=1)
    await send(dispatcher, session, "hola", chat_id=1, user_id=1)
    await send(dispatcher, session, "hello", chat_id=1, user_id=1)

    # Assert
    assert session.edits == ["Deck: Spanish. Send the front side."]
    assert session.answers == ["Choose a deck:", "Send the back side.", "Card added to Spanish."]


async def test_user_can_choose_a_deck_while_adding_a_card(
    dispatcher: Dispatcher, selected_decks: FakeSelectedDeckStore
) -> None:
    """The deck picked inside /addcard is remembered, so the next card lands there without re-picking."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=10, user_id=10)
    await pick_deck(dispatcher, session, SPANISH_DECK_ID, chat_id=10, user_id=10)
    await send(dispatcher, session, "hola", chat_id=10, user_id=10)
    await send(dispatcher, session, "hello", chat_id=10, user_id=10)

    # Assert
    assert session.last_answer == "Card added to Spanish."
    assert selected_decks.decks[10] == SPANISH_DECK_ID


async def test_user_cannot_submit_an_empty_front(dispatcher: Dispatcher) -> None:
    """An empty front is rejected and re-asked, without advancing past the front step."""
    # Arrange
    bot = make_bot(RecordingSession())
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=2, user_id=2)
    await pick_deck(dispatcher, session, DEFAULT_DECK_ID, chat_id=2, user_id=2)
    await send(dispatcher, session, "   ", chat_id=2, user_id=2)

    # Assert
    assert session.last_answer == "The front side can't be empty. Send the front side."
    context = dispatcher.fsm.resolve_context(bot, chat_id=2, user_id=2)
    assert context is not None
    assert await context.get_state() == AddCard.waiting_for_front.state


async def test_user_cannot_add_a_card_without_authenticating(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway
) -> None:
    """A session-expired failure from AnkiWeb tells the user to authenticate, not a generic error."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=3, user_id=3)
    await pick_deck(dispatcher, session, DEFAULT_DECK_ID, chat_id=3, user_id=3)
    await send(dispatcher, session, "front", chat_id=3, user_id=3)
    card_gateway.error = AnkiSessionExpiredError()
    await send(dispatcher, session, "back", chat_id=3, user_id=3)

    # Assert
    assert session.last_answer == "Run /auth first."


async def test_user_cannot_add_a_card_when_ankiweb_fails(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway
) -> None:
    """Any other AnkiWeb failure produces the generic retry message, not a stack trace."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=4, user_id=4)
    await pick_deck(dispatcher, session, DEFAULT_DECK_ID, chat_id=4, user_id=4)
    await send(dispatcher, session, "front", chat_id=4, user_id=4)
    card_gateway.error = AnkiCardCreationError()
    await send(dispatcher, session, "back", chat_id=4, user_id=4)

    # Assert
    assert session.last_answer == "Failed to add the card to AnkiWeb. Please try again later."


async def test_operator_can_see_the_reason_behind_a_generic_failure(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway, caplog: pytest.LogCaptureFixture
) -> None:
    """The generic retry reply hides the reason from the user, but it still reaches the log."""
    # Arrange
    session = RecordingSession()

    # Act
    with caplog.at_level(logging.WARNING):
        await send(dispatcher, session, "/addcard", chat_id=9, user_id=9)
        await pick_deck(dispatcher, session, DEFAULT_DECK_ID, chat_id=9, user_id=9)
        await send(dispatcher, session, "front", chat_id=9, user_id=9)
        card_gateway.error = AnkiCardCreationError("distinctive-boom-reason")
        await send(dispatcher, session, "back", chat_id=9, user_id=9)

    # Assert
    assert "distinctive-boom-reason" in caplog.text


async def test_user_cannot_add_a_card_to_a_deck_that_no_longer_exists(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway
) -> None:
    """A deck deleted between picking and sending the back side is named, not reported generically."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=12, user_id=12)
    await pick_deck(dispatcher, session, SPANISH_DECK_ID, chat_id=12, user_id=12)
    await send(dispatcher, session, "front", chat_id=12, user_id=12)
    card_gateway.decks = {DEFAULT_DECK_ID: "Default"}
    await send(dispatcher, session, "back", chat_id=12, user_id=12)

    # Assert
    assert session.last_answer == "That deck no longer exists in AnkiWeb. Run /decks again."


async def test_user_cannot_start_adding_a_card_when_ankiweb_is_unreachable(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway
) -> None:
    """A failure fetching the decks ends /addcard immediately instead of opening a dialog."""
    # Arrange
    bot = make_bot(RecordingSession())
    deck_gateway.error = AnkiDeckListingError()
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=13, user_id=13)

    # Assert
    assert session.last_answer == "Failed to reach AnkiWeb. Please try again later."
    context = dispatcher.fsm.resolve_context(bot, chat_id=13, user_id=13)
    assert context is not None
    assert await context.get_state() is None


async def test_user_cannot_add_a_card_to_a_notetype_without_two_fields(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway
) -> None:
    """A current notetype that isn't front/back-shaped tells the user to switch it, not a generic error."""
    # Arrange
    card_gateway.field_count = 8
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=8, user_id=8)
    await pick_deck(dispatcher, session, DEFAULT_DECK_ID, chat_id=8, user_id=8)
    await send(dispatcher, session, "front", chat_id=8, user_id=8)
    await send(dispatcher, session, "back", chat_id=8, user_id=8)

    # Assert
    assert session.last_answer == (
        "AnkiWeb's current notetype isn't set up for a simple front/back card. "
        "Switch to a two-field notetype (e.g. Basic) in AnkiWeb's editor and try again."
    )


async def test_user_can_cancel_mid_dialog(dispatcher: Dispatcher) -> None:
    """/cancel exits the dialog, and a following plain message is no longer treated as a card side."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=5, user_id=5)
    await pick_deck(dispatcher, session, DEFAULT_DECK_ID, chat_id=5, user_id=5)
    await send(dispatcher, session, "/cancel", chat_id=5, user_id=5)
    await send(dispatcher, session, "just chatting", chat_id=5, user_id=5)

    # Assert
    assert session.answers == ["Choose a deck:", "Cancelled."]


async def test_two_users_can_add_cards_concurrently_without_state_mixing(dispatcher: Dispatcher) -> None:
    """Two users in the same chat run the dialog at once, and neither sees the other's step.

    Same ``chat_id``, different ``user_id`` — the default FSM strategy keys state by both, so this
    is the scenario a wrong storage key would leak: interleaved awaits under ``asyncio.gather``
    against the real ``MemoryStorage`` behind ``dispatcher``.
    """
    # Arrange
    session_a = RecordingSession()
    session_b = RecordingSession()

    async def run_dialog(session: RecordingSession, user_id: int, front: str, back: str) -> None:
        await send(dispatcher, session, "/addcard", chat_id=6, user_id=user_id)
        await pick_deck(dispatcher, session, DEFAULT_DECK_ID, chat_id=6, user_id=user_id)
        await send(dispatcher, session, front, chat_id=6, user_id=user_id)
        await send(dispatcher, session, back, chat_id=6, user_id=user_id)

    # Act
    await asyncio.gather(
        run_dialog(session_a, 6, "bonjour", "hello"),
        run_dialog(session_b, 7, "hola", "hello"),
    )

    # Assert
    expected = ["Choose a deck:", "Send the back side.", "Card added to Default."]
    assert session_a.answers == expected
    assert session_b.answers == expected


async def test_two_users_can_keep_different_selected_decks(dispatcher: Dispatcher) -> None:
    """Two concurrent dialogs in one chat each land their card in the deck that user picked.

    A store keyed by chat rather than by user would show up here and nowhere else.
    """
    # Arrange
    session_a = RecordingSession()
    session_b = RecordingSession()

    async def run_dialog(session: RecordingSession, user_id: int, deck_id: int) -> None:
        await send(dispatcher, session, "/addcard", chat_id=7, user_id=user_id)
        await pick_deck(dispatcher, session, deck_id, chat_id=7, user_id=user_id)
        await send(dispatcher, session, "front", chat_id=7, user_id=user_id)
        await send(dispatcher, session, "back", chat_id=7, user_id=user_id)

    # Act
    await asyncio.gather(
        run_dialog(session_a, 20, DEFAULT_DECK_ID),
        run_dialog(session_b, 21, SPANISH_DECK_ID),
    )

    # Assert
    assert session_a.last_answer == "Card added to Default."
    assert session_b.last_answer == "Card added to Spanish."
