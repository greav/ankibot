"""The /auth outcomes, each driven through the composed dispatcher rather than by calling the handler.

Going through ``feed_update`` covers the ``Command("auth")`` filter, router order and aiogram's
injection by parameter name on top of the handler body. A directly-called handler covers none of
those three, so a typo in the filter would leave every test here green while the bot answers nothing.
"""

import logging

import pytest
from aiogram import Dispatcher
from aiogram.types import Update

from ankibot.application.exceptions.anki import (
    AnkiAuthenticationError,
    AnkiInvalidPasswordError,
    AnkiInvalidUsernameError,
)
from tests.common.fakes.anki_authenticator import FakeAnkiAuthenticator
from tests.common.telegram import RecordingSession, make_bot, make_message


async def run_auth(
    dispatcher: Dispatcher,
    authenticator: FakeAnkiAuthenticator,
    error: Exception | None,
) -> RecordingSession:
    """Feed /auth to the dispatcher with the authenticator configured to fail in a given way."""
    authenticator.error = error
    session = RecordingSession()
    bot = make_bot(session)
    update = Update(update_id=1, message=make_message(bot, text="/auth"))
    await dispatcher.feed_update(bot, update)
    return session


async def test_user_can_see_authentication_confirmed(
    dispatcher: Dispatcher,
    authenticator: FakeAnkiAuthenticator,
) -> None:
    """/auth reaches its handler with its dependency injected, and confirms once AnkiWeb accepts.

    The exact text is what makes this a wiring test too: a mismatched dependency key raises
    ``TypeError`` inside the handler call, which the errors router turns into its own reply — so
    asserting merely that *some* answer came back would pass with the injection broken.
    """
    # Arrange / Act
    session = await run_auth(dispatcher, authenticator, None)

    # Assert
    assert session.last_answer == "Authenticated with AnkiWeb."


async def test_user_can_see_that_the_username_was_rejected(
    dispatcher: Dispatcher,
    authenticator: FakeAnkiAuthenticator,
) -> None:
    """/auth names the username specifically when AnkiWeb rejects it."""
    # Arrange / Act
    session = await run_auth(dispatcher, authenticator, AnkiInvalidUsernameError())

    # Assert
    assert session.last_answer == "AnkiWeb rejected the configured username."


async def test_user_can_see_that_the_password_was_rejected(
    dispatcher: Dispatcher,
    authenticator: FakeAnkiAuthenticator,
) -> None:
    """/auth names the password specifically when AnkiWeb rejects it."""
    # Arrange / Act
    session = await run_auth(dispatcher, authenticator, AnkiInvalidPasswordError())

    # Assert
    assert session.last_answer == "AnkiWeb rejected the configured password."


async def test_user_can_see_a_retry_message_on_any_other_failure(
    dispatcher: Dispatcher,
    authenticator: FakeAnkiAuthenticator,
) -> None:
    """Any other authentication failure produces the generic retry message, not a stack trace."""
    # Arrange / Act
    session = await run_auth(dispatcher, authenticator, AnkiAuthenticationError())

    # Assert
    assert session.last_answer == "Failed to authenticate with AnkiWeb. Please try again later."


async def test_operator_can_see_the_reason_behind_a_generic_failure(
    dispatcher: Dispatcher,
    authenticator: FakeAnkiAuthenticator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The generic retry reply hides the reason from the user, but it still reaches the log."""
    # Arrange / Act
    with caplog.at_level(logging.WARNING):
        await run_auth(dispatcher, authenticator, AnkiAuthenticationError("distinctive-boom-reason"))

    # Assert
    assert "distinctive-boom-reason" in caplog.text
