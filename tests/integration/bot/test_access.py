"""The allowlist gate: a user not on it gets silence, whatever kind of update they send.

Through the dispatcher on purpose — the gate is an outer middleware on the ``update`` observer,
so only a fed ``Update`` proves it sits in front of every router.
"""

from aiogram import Dispatcher
from aiogram.types import Update

from tests.common.telegram import RecordingSession, make_bot, make_callback_query, make_message
from tests.integration.bot.conftest import MAX_ALLOWED_TEST_USER_ID

STRANGER_ID = MAX_ALLOWED_TEST_USER_ID + 1


async def test_stranger_cannot_get_any_reply_from_the_bot(dispatcher: Dispatcher) -> None:
    """A message from a user not on the allowlist is dropped before any handler: nothing is sent at all."""
    # Arrange
    session = RecordingSession()
    bot = make_bot(session)
    update = Update(update_id=1, message=make_message(bot, text="/start", user_id=STRANGER_ID))

    # Act
    await dispatcher.feed_update(bot, update)

    # Assert — not merely "no SendMessage": no API call of any kind left the bot.
    assert session.requests == []


async def test_stranger_cannot_reach_callback_handlers(dispatcher: Dispatcher) -> None:
    """The gate covers non-message updates too: a stranger's button tap is dropped, not even answered."""
    # Arrange
    session = RecordingSession()
    bot = make_bot(session)
    update = Update(update_id=1, callback_query=make_callback_query(bot, "deck:1", user_id=STRANGER_ID))

    # Act
    await dispatcher.feed_update(bot, update)

    # Assert
    assert session.requests == []
