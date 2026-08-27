from aiogram import Dispatcher
from aiogram.types import Update

from tests.common.telegram import RecordingSession, make_bot, make_message


async def test_user_can_see_what_to_do_after_start(dispatcher: Dispatcher) -> None:
    """/start is routed to its handler and answers with the greeting telling the user what to do next."""
    # Arrange
    session = RecordingSession()
    bot = make_bot(session)
    update = Update(update_id=1, message=make_message(bot, text="/start"))

    # Act
    await dispatcher.feed_update(bot, update)

    # Assert
    assert session.last_answer == "Hi, send any message!"
