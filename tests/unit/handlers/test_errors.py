"""The one handler branch the dispatcher cannot deliver, so it is called directly.

Reaching the errors router needs a handler that raises, and the branch under test is the one where
the update carries no message — a callback query, an edited post. The bot registers no handler for
those, so no ``feed_update`` ever reaches this branch. Everything else lives in ``tests/integration/bot/``.
"""

import logging

import pytest
from aiogram.types import ErrorEvent, Update

from ankibot.presentation.handlers.errors import unexpected_error_handler


async def test_user_cannot_lose_an_error_report_on_an_update_without_a_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An update carrying no message still gets its failure logged, instead of crashing the error handler.

    The reply branch needs a message; an update that has none (a callback query, an edited post)
    would take the alternative branch, and a handler that assumed a message would raise a second
    time from inside the last-resort handler, leaving nothing in the log either.
    """
    # Arrange
    event = ErrorEvent(update=Update(update_id=7), exception=RuntimeError("unexpected"))

    # Act
    with caplog.at_level(logging.ERROR):
        await unexpected_error_handler(event)

    # Assert
    assert any(record.levelno == logging.ERROR for record in caplog.records)
