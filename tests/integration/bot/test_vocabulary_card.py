"""The word -> generated card dialog, driven through the composed dispatcher.

Going through ``feed_update`` covers the catch-all's ``StateFilter``/router-order guarantees on top
of the handler bodies, in particular that it stays out of /addcard's way.
"""

import asyncio
import logging
from typing import Literal

import pytest
from aiogram import Dispatcher
from aiogram.methods import EditMessageReplyMarkup, SendMessage
from aiogram.types import Update

from ankibot.application.exceptions.anki import (
    AnkiCardCreationError,
    AnkiSessionExpiredError,
    AnkiTemplateTargetNotFoundError,
)
from ankibot.application.exceptions.generation import CardGenerationUnavailableError
from ankibot.domain.card_template import CardTemplate
from ankibot.presentation.keyboards.decks import DeckCallback
from ankibot.presentation.keyboards.generated_card import GeneratedCardCallback
from tests.common.fakes.card_generator import FakeCardGenerator
from tests.common.fakes.vocabulary_card_gateway import FakeVocabularyCardGateway
from tests.common.telegram import RecordingSession, make_bot, make_callback_query, make_message

DEFAULT_DECK_ID = 1


async def send(dispatcher: Dispatcher, session: RecordingSession, text: str, *, chat_id: int, user_id: int) -> None:
    """Feed one plain message from (chat_id, user_id) to the dispatcher, no response queued.

    For a call whose reply the handler never reads back (a failure reply, or a step of /addcard).
    """
    bot = make_bot(session)
    update = Update(update_id=1, message=make_message(bot, text=text, chat_id=chat_id, user_id=user_id))
    await dispatcher.feed_update(bot, update)


async def send_word(
    dispatcher: Dispatcher,
    session: RecordingSession,
    word: str,
    *,
    chat_id: int,
    user_id: int,
    preview_message_id: int = 100,
) -> None:
    """Send a word that is expected to produce a preview, queuing the sendMessage response it reads back."""
    bot = make_bot(session)
    session.queue_response(
        SendMessage, make_message(bot, message_id=preview_message_id, chat_id=chat_id, user_id=user_id)
    )
    update = Update(update_id=1, message=make_message(bot, text=word, chat_id=chat_id, user_id=user_id))
    await dispatcher.feed_update(bot, update)


async def pick_deck(
    dispatcher: Dispatcher, session: RecordingSession, deck_id: int, *, chat_id: int, user_id: int
) -> None:
    """Tap a deck on the picker /addcard opens with."""
    bot = make_bot(session)
    callback = make_callback_query(bot, DeckCallback(id=deck_id).pack(), chat_id=chat_id, user_id=user_id)
    await dispatcher.feed_update(bot, Update(update_id=2, callback_query=callback))


async def tap_action(
    dispatcher: Dispatcher,
    session: RecordingSession,
    action: Literal["save", "regenerate", "cancel"],
    *,
    chat_id: int,
    user_id: int,
    preview_message_id: int = 200,
) -> None:
    """Tap Save/Regenerate/Cancel on the pending preview.

    Regenerate sends a fresh preview and so needs a queued sendMessage response, like ``send_word``.
    """
    bot = make_bot(session)
    if action == "regenerate":
        session.queue_response(
            SendMessage, make_message(bot, message_id=preview_message_id, chat_id=chat_id, user_id=user_id)
        )
    callback = make_callback_query(bot, GeneratedCardCallback(action=action).pack(), chat_id=chat_id, user_id=user_id)
    await dispatcher.feed_update(bot, Update(update_id=3, callback_query=callback))


async def test_user_can_generate_a_card_preview(dispatcher: Dispatcher) -> None:
    """A plain word produces a preview naming the deck and every field the notetype carries."""
    # Arrange
    session = RecordingSession()

    # Act
    await send_word(dispatcher, session, "serendipity", chat_id=1, user_id=1)

    # Assert
    assert session.last_answer == (
        "Add to English Words V2?\n\nWord: serendipity\nMeaning: a pleasant surprise\nExample: What a serendipity!"
    )


async def test_user_can_save_the_generated_card(dispatcher: Dispatcher) -> None:
    """Tapping Save adds the note and confirms which deck it landed in."""
    # Arrange
    session = RecordingSession()

    # Act
    await send_word(dispatcher, session, "serendipity", chat_id=2, user_id=2)
    await tap_action(dispatcher, session, "save", chat_id=2, user_id=2)

    # Assert
    assert session.last_edit == "Added to English Words V2."


async def test_user_can_regenerate_and_then_save(dispatcher: Dispatcher) -> None:
    """Regenerate strips the stale keyboard and replaces the preview with a fresh, still-savable one."""
    # Arrange
    session = RecordingSession()

    # Act
    await send_word(dispatcher, session, "serendipity", chat_id=3, user_id=3)
    await tap_action(dispatcher, session, "regenerate", chat_id=3, user_id=3, preview_message_id=301)
    await tap_action(dispatcher, session, "save", chat_id=3, user_id=3)

    # Assert
    assert len(session.answers) == 2
    assert any(isinstance(request, EditMessageReplyMarkup) for request in session.requests)
    assert session.last_edit == "Added to English Words V2."


async def test_user_can_cancel_the_preview(dispatcher: Dispatcher) -> None:
    """Cancel drops the preview and clears the pending state."""
    # Arrange
    bot = make_bot(RecordingSession())
    session = RecordingSession()

    # Act
    await send_word(dispatcher, session, "serendipity", chat_id=4, user_id=4)
    await tap_action(dispatcher, session, "cancel", chat_id=4, user_id=4)

    # Assert
    assert session.last_edit == "Cancelled."
    context = dispatcher.fsm.resolve_context(bot, chat_id=4, user_id=4)
    assert context is not None
    assert await context.get_state() is None


async def test_user_cannot_generate_a_card_when_the_generator_is_unavailable(
    dispatcher: Dispatcher, card_generator: FakeCardGenerator
) -> None:
    """A generator that can't be reached tells the user to retry later, not a generic error."""
    # Arrange
    session = RecordingSession()
    card_generator.error = CardGenerationUnavailableError()

    # Act
    await send(dispatcher, session, "serendipity", chat_id=5, user_id=5)

    # Assert
    assert session.last_answer == "The card generator is unavailable. Please try again later."


async def test_user_cannot_generate_a_card_when_fields_are_left_incomplete(
    dispatcher: Dispatcher, card_generator: FakeCardGenerator
) -> None:
    """A generator that leaves fields empty produces a retry-or-rephrase reply, not a stack trace."""
    # Arrange
    session = RecordingSession()
    card_generator.values = {"Word": "serendipity"}

    # Act
    await send(dispatcher, session, "serendipity", chat_id=6, user_id=6)

    # Assert
    assert session.last_answer == "Couldn't generate a card for that word. Try again, or rephrase it."


async def test_user_cannot_generate_a_card_without_authenticating(
    dispatcher: Dispatcher, vocabulary_card_gateway: FakeVocabularyCardGateway
) -> None:
    """A session-expired failure tells the user to authenticate, not a generic error."""
    # Arrange
    session = RecordingSession()
    vocabulary_card_gateway.error = AnkiSessionExpiredError()

    # Act
    await send(dispatcher, session, "serendipity", chat_id=7, user_id=7)

    # Assert
    assert session.last_answer == "Run /auth first."


async def test_user_cannot_generate_a_card_when_the_target_is_misconfigured(
    dispatcher: Dispatcher, vocabulary_card_gateway: FakeVocabularyCardGateway
) -> None:
    """A missing configured deck/notetype is named to the user, not reported generically."""
    # Arrange
    session = RecordingSession()
    vocabulary_card_gateway.error = AnkiTemplateTargetNotFoundError("distinctive-target-reason")

    # Act
    await send(dispatcher, session, "serendipity", chat_id=8, user_id=8)

    # Assert
    assert session.last_answer == "distinctive-target-reason"


async def test_operator_can_see_the_reason_behind_a_generic_generation_failure(
    dispatcher: Dispatcher, vocabulary_card_gateway: FakeVocabularyCardGateway, caplog: pytest.LogCaptureFixture
) -> None:
    """The generic retry reply hides the reason from the user, but it still reaches the log."""
    # Arrange
    session = RecordingSession()
    vocabulary_card_gateway.error = AnkiCardCreationError("distinctive-generate-boom-reason")

    # Act
    with caplog.at_level(logging.WARNING):
        await send(dispatcher, session, "serendipity", chat_id=9, user_id=9)

    # Assert
    assert "distinctive-generate-boom-reason" in caplog.text


async def test_user_cannot_save_a_card_when_the_session_has_expired(
    dispatcher: Dispatcher, vocabulary_card_gateway: FakeVocabularyCardGateway
) -> None:
    """A session that expires between preview and Save tells the user to authenticate."""
    # Arrange
    session = RecordingSession()
    await send_word(dispatcher, session, "serendipity", chat_id=10, user_id=10)
    vocabulary_card_gateway.error = AnkiSessionExpiredError()

    # Act
    await tap_action(dispatcher, session, "save", chat_id=10, user_id=10)

    # Assert
    assert session.last_edit == "Run /auth first."


async def test_user_cannot_save_a_card_when_the_target_is_misconfigured(
    dispatcher: Dispatcher, vocabulary_card_gateway: FakeVocabularyCardGateway
) -> None:
    """A deck/notetype that disappears between preview and Save is named, not reported generically."""
    # Arrange
    session = RecordingSession()
    await send_word(dispatcher, session, "serendipity", chat_id=11, user_id=11)
    vocabulary_card_gateway.error = AnkiTemplateTargetNotFoundError("distinctive-target-reason")

    # Act
    await tap_action(dispatcher, session, "save", chat_id=11, user_id=11)

    # Assert
    assert session.last_edit == "distinctive-target-reason"


async def test_user_cannot_save_a_card_when_ankiweb_fails(
    dispatcher: Dispatcher, vocabulary_card_gateway: FakeVocabularyCardGateway
) -> None:
    """Any other AnkiWeb failure on Save produces the generic retry message, not a stack trace."""
    # Arrange
    session = RecordingSession()
    await send_word(dispatcher, session, "serendipity", chat_id=12, user_id=12)
    vocabulary_card_gateway.error = AnkiCardCreationError()

    # Act
    await tap_action(dispatcher, session, "save", chat_id=12, user_id=12)

    # Assert
    assert session.last_edit == "Failed to add the card to AnkiWeb. Please try again later."


async def test_user_cannot_save_a_card_when_the_notetype_gained_a_field(
    dispatcher: Dispatcher, vocabulary_card_gateway: FakeVocabularyCardGateway
) -> None:
    """A notetype edited (a field added) between preview and Save is caught, not written short."""
    # Arrange
    session = RecordingSession()
    await send_word(dispatcher, session, "serendipity", chat_id=13, user_id=13)
    vocabulary_card_gateway.template = CardTemplate(
        name="English Words V2", fields=("Word", "Meaning", "Example", "Notes")
    )

    # Act
    await tap_action(dispatcher, session, "save", chat_id=13, user_id=13)

    # Assert
    assert session.last_edit == "Couldn't generate a card for that word. Try again, or rephrase it."


async def test_plain_text_is_not_intercepted_while_addcard_is_mid_dialog(dispatcher: Dispatcher) -> None:
    """A plain message sent while /addcard's dialog is active is still treated as a card side, not a word."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/addcard", chat_id=14, user_id=14)
    await pick_deck(dispatcher, session, DEFAULT_DECK_ID, chat_id=14, user_id=14)
    await send(dispatcher, session, "front-text", chat_id=14, user_id=14)

    # Assert
    assert session.answers[-1] == "Send the back side."


async def test_two_users_can_generate_previews_concurrently_without_state_mixing(dispatcher: Dispatcher) -> None:
    """Two users in the same chat run the dialog at once, and neither's Save answers for the other.

    Same ``chat_id``, different ``user_id`` — the default FSM strategy keys state by both, so this is
    the scenario a wrong storage key would leak: interleaved awaits under ``asyncio.gather``.
    """
    # Arrange
    session_a = RecordingSession()
    session_b = RecordingSession()

    async def run_dialog(session: RecordingSession, user_id: int, preview_message_id: int) -> None:
        await send_word(
            dispatcher, session, "serendipity", chat_id=15, user_id=user_id, preview_message_id=preview_message_id
        )
        await tap_action(dispatcher, session, "save", chat_id=15, user_id=user_id)

    # Act
    await asyncio.gather(run_dialog(session_a, 30, 401), run_dialog(session_b, 31, 402))

    # Assert
    assert session_a.last_edit == "Added to English Words V2."
    assert session_b.last_edit == "Added to English Words V2."
