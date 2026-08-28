"""The /addcard dialog outcomes, driven through the composed dispatcher rather than by calling
handlers directly.

Going through ``feed_update`` covers the command filters, router order (``/cancel`` winning inside
a state) and aiogram's injection by parameter name on top of the handler bodies.
"""

import asyncio
import logging

import pytest
from aiogram import Dispatcher
from aiogram.types import Update

from ankibot.application.exceptions.anki import AnkiCardCreationError, AnkiSessionExpiredError
from ankibot.application.manage_cards.create_card import AddTarget
from ankibot.presentation.handlers.add_card import AddCard
from tests.common.fakes.card_gateway import FakeCardGateway
from tests.common.telegram import RecordingSession, make_bot, make_message


async def send(dispatcher: Dispatcher, session: RecordingSession, text: str, *, chat_id: int, user_id: int) -> None:
    """Feed one message from (chat_id, user_id) to the dispatcher, replies landing in ``session``."""
    bot = make_bot(session)
    update = Update(update_id=1, message=make_message(bot, text=text, chat_id=chat_id, user_id=user_id))
    await dispatcher.feed_update(bot, update)


async def test_user_can_add_a_card(dispatcher: Dispatcher, card_gateway: FakeCardGateway) -> None:
    """A full front/back dialog ends with a reply naming the deck the fake gateway reports as current."""
    # Arrange
    card_gateway.target = AddTarget(deck_id=1, notetype_id=1, deck_name="Spanish", field_count=2)
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=1, user_id=1)
    await send(dispatcher, session, "hola", chat_id=1, user_id=1)
    await send(dispatcher, session, "hello", chat_id=1, user_id=1)

    # Assert
    assert session.answers == ["Send the front side.", "Send the back side.", "Card added to Spanish."]


async def test_user_cannot_submit_an_empty_front(dispatcher: Dispatcher) -> None:
    """An empty front is rejected and re-asked, without advancing past the front step."""
    # Arrange
    bot = make_bot(RecordingSession())
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=2, user_id=2)
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
    card_gateway.error = AnkiSessionExpiredError()
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=3, user_id=3)
    await send(dispatcher, session, "front", chat_id=3, user_id=3)
    await send(dispatcher, session, "back", chat_id=3, user_id=3)

    # Assert
    assert session.last_answer == "Run /auth first."


async def test_user_cannot_add_a_card_when_ankiweb_fails(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway
) -> None:
    """Any other AnkiWeb failure produces the generic retry message, not a stack trace."""
    # Arrange
    card_gateway.error = AnkiCardCreationError()
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=4, user_id=4)
    await send(dispatcher, session, "front", chat_id=4, user_id=4)
    await send(dispatcher, session, "back", chat_id=4, user_id=4)

    # Assert
    assert session.last_answer == "Failed to add the card to AnkiWeb. Please try again later."


async def test_operator_can_see_the_reason_behind_a_generic_failure(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway, caplog: pytest.LogCaptureFixture
) -> None:
    """The generic retry reply hides the reason from the user, but it still reaches the log."""
    # Arrange
    card_gateway.error = AnkiCardCreationError("distinctive-boom-reason")
    session = RecordingSession()

    # Act
    with caplog.at_level(logging.WARNING):
        await send(dispatcher, session, "/addcard", chat_id=9, user_id=9)
        await send(dispatcher, session, "front", chat_id=9, user_id=9)
        await send(dispatcher, session, "back", chat_id=9, user_id=9)

    # Assert
    assert "distinctive-boom-reason" in caplog.text


async def test_user_cannot_add_a_card_to_a_notetype_without_two_fields(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway
) -> None:
    """A current notetype that isn't front/back-shaped tells the user to switch it, not a generic error."""
    # Arrange
    card_gateway.target = AddTarget(deck_id=1, notetype_id=1, deck_name="Vocabulary", field_count=8)
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=8, user_id=8)
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
    await send(dispatcher, session, "/cancel", chat_id=5, user_id=5)
    await send(dispatcher, session, "just chatting", chat_id=5, user_id=5)

    # Assert
    assert session.answers == ["Send the front side.", "Cancelled."]


async def test_two_users_can_add_cards_concurrently_without_state_mixing(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway
) -> None:
    """Two users in the same chat run the dialog at once, and neither sees the other's step.

    Same ``chat_id``, different ``user_id`` — the default FSM strategy keys state by both, so this
    is the scenario a wrong storage key would leak: interleaved awaits under ``asyncio.gather``
    against the real ``MemoryStorage`` behind ``dispatcher``.
    """
    # Arrange
    card_gateway.target = AddTarget(deck_id=1, notetype_id=1, deck_name="Default", field_count=2)
    session_a = RecordingSession()
    session_b = RecordingSession()

    async def run_dialog(session: RecordingSession, user_id: int, front: str, back: str) -> None:
        await send(dispatcher, session, "/addcard", chat_id=6, user_id=user_id)
        await send(dispatcher, session, front, chat_id=6, user_id=user_id)
        await send(dispatcher, session, back, chat_id=6, user_id=user_id)

    # Act
    await asyncio.gather(
        run_dialog(session_a, 6, "bonjour", "hello"),
        run_dialog(session_b, 7, "hola", "hello"),
    )

    # Assert
    expected = ["Send the front side.", "Send the back side.", "Card added to Default."]
    assert session_a.answers == expected
    assert session_b.answers == expected
