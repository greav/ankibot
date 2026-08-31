"""The rule that decides who an update is from.

Lives here rather than in ``tests/integration/bot`` because it answers a question about a Telegram
object alone: no router, no dispatcher and no interactor take part in it.
"""

from datetime import UTC, datetime

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User

from ankibot.presentation.identity import NoTelegramUserError, telegram_user_id


def make_message(user: User | None) -> Message:
    """A message from ``user``, or the senderless one Telegram delivers for a channel post."""
    return Message(message_id=1, date=datetime.now(UTC), chat=Chat(id=7, type="private"), from_user=user)


def test_bot_can_attribute_a_message_to_its_sender() -> None:
    """A message from a real account is filed under that account's Telegram id."""
    # Arrange
    message = make_message(User(id=42, is_bot=False, first_name="Test"))

    # Act
    user_id = telegram_user_id(message)

    # Assert
    assert user_id == 42


def test_bot_can_attribute_a_button_tap_to_its_sender() -> None:
    """A tap is filed under the account that tapped, not under the message it was attached to."""
    # Arrange
    callback = CallbackQuery(
        id="1",
        from_user=User(id=42, is_bot=False, first_name="Test"),
        chat_instance="1",
        data="deck:1",
        message=make_message(User(id=99, is_bot=False, first_name="Other")),
    )

    # Act
    user_id = telegram_user_id(callback)

    # Assert
    assert user_id == 42


def test_bot_cannot_attribute_an_update_that_carries_no_sender() -> None:
    """A senderless update is refused rather than filed under a placeholder shared by all of them.

    A channel post, an anonymous group admin's message and an automatic forward all arrive this way,
    so a placeholder id would let strangers share one selected deck.
    """
    # Arrange
    message = make_message(None)

    # Act / Assert
    with pytest.raises(NoTelegramUserError):
        telegram_user_id(message)
