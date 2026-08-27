"""Wiring guarantees no single handler can give: what the dispatcher itself does with an update.

Routing and dependency injection are covered where they are also the point of the scenario — see
``test_authenticate``. What is left here is the errors router, which nothing else can reach.
"""

from aiogram import Dispatcher
from aiogram.types import Update

from tests.common.fakes.anki_authenticator import FakeAnkiAuthenticator
from tests.common.telegram import RecordingSession, make_bot, make_message


async def test_user_can_see_a_reply_when_a_handler_crashes(
    dispatcher: Dispatcher,
    authenticator: FakeAnkiAuthenticator,
) -> None:
    """An error no handler expected still reaches the user as a reply, not only the log.

    Only the dispatcher routes an escaped exception to the errors router, so this guarantee is
    unreachable by calling a handler directly.
    """
    # Arrange — the failure is outside the ApplicationError hierarchy, so /auth's except-chain
    # lets it escape to the errors router.
    authenticator.error = RuntimeError("unexpected")
    session = RecordingSession()
    bot = make_bot(session)
    update = Update(update_id=1, message=make_message(bot, text="/auth"))

    # Act
    await dispatcher.feed_update(bot, update)

    # Assert
    assert session.last_answer == "Something went wrong. Please try again later."
