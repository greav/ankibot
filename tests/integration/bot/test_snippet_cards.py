"""The snippet → generated cards dialog, driven through the composed dispatcher.

Going through ``feed_update`` covers the routing split with the vocabulary-word catch-all (long
text and images land here, a short word still there), the /snippet waiting state, and dishka's
injection, on top of the handler bodies.
"""

from typing import Literal

from aiogram import Dispatcher
from aiogram.methods import SendMessage
from aiogram.types import Update

from ankibot.application.add_snippet_cards import DraftCard
from ankibot.application.exceptions.anki import AnkiSessionExpiredError
from ankibot.application.exceptions.generation import CardGenerationUnavailableError
from ankibot.presentation.keyboards.generated_card import GeneratedCardCallback
from tests.common.fakes.card_gateway import FakeCardGateway
from tests.common.fakes.snippet_cards_generator import FakeSnippetCardsGenerator
from tests.common.telegram import (
    RecordingSession,
    make_bot,
    make_callback_query,
    make_message,
    make_photo_message,
    queue_file_download,
)

LONG_TEXT = (
    "The Global Interpreter Lock is a mutex protecting access to Python objects, "
    "preventing multiple native threads from executing Python bytecode at once."
)

EXPECTED_PREVIEW = (
    "Add 2 cards to Default?\n\n"
    "1. What does GIL stand for?\n— Global Interpreter Lock\n\n"
    "2. Which lock serializes Python bytecode execution?\n— The GIL"
)


async def send(dispatcher: Dispatcher, session: RecordingSession, text: str, *, chat_id: int, user_id: int) -> None:
    """Feed one plain message whose reply the handler never reads back (a failure reply, /snippet)."""
    bot = make_bot(session)
    update = Update(update_id=1, message=make_message(bot, text=text, chat_id=chat_id, user_id=user_id))
    await dispatcher.feed_update(bot, update)


async def send_snippet(
    dispatcher: Dispatcher,
    session: RecordingSession,
    text: str,
    *,
    chat_id: int,
    user_id: int,
    preview_message_id: int = 100,
) -> None:
    """Send text expected to produce a preview, queuing the sendMessage response it reads back."""
    bot = make_bot(session)
    session.queue_response(
        SendMessage, make_message(bot, message_id=preview_message_id, chat_id=chat_id, user_id=user_id)
    )
    update = Update(update_id=1, message=make_message(bot, text=text, chat_id=chat_id, user_id=user_id))
    await dispatcher.feed_update(bot, update)


async def send_photo(
    dispatcher: Dispatcher,
    session: RecordingSession,
    *,
    caption: str | None = None,
    chat_id: int,
    user_id: int,
    preview_message_id: int = 100,
) -> None:
    """Send a photo, queuing its download pair and the sendMessage response the preview reads back."""
    bot = make_bot(session)
    queue_file_download(session, b"fake-jpeg-bytes")
    session.queue_response(
        SendMessage, make_message(bot, message_id=preview_message_id, chat_id=chat_id, user_id=user_id)
    )
    photo = make_photo_message(bot, caption=caption, chat_id=chat_id, user_id=user_id)
    await dispatcher.feed_update(bot, Update(update_id=1, message=photo))


async def tap_action(
    dispatcher: Dispatcher,
    session: RecordingSession,
    action: Literal["save", "regenerate", "cancel"],
    *,
    chat_id: int,
    user_id: int,
    preview_message_id: int = 200,
) -> None:
    """Tap Save/Regenerate/Cancel on the pending preview."""
    bot = make_bot(session)
    if action == "regenerate":
        session.queue_response(
            SendMessage, make_message(bot, message_id=preview_message_id, chat_id=chat_id, user_id=user_id)
        )
    callback = make_callback_query(bot, GeneratedCardCallback(action=action).pack(), chat_id=chat_id, user_id=user_id)
    await dispatcher.feed_update(bot, Update(update_id=3, callback_query=callback))


async def test_user_can_generate_cards_from_a_long_text(dispatcher: Dispatcher) -> None:
    """A pasted passage produces a preview naming the deck and listing every generated card."""
    # Arrange
    session = RecordingSession()

    # Act
    await send_snippet(dispatcher, session, LONG_TEXT, chat_id=1, user_id=1)

    # Assert
    assert session.last_answer == EXPECTED_PREVIEW


async def test_user_can_save_the_generated_cards(dispatcher: Dispatcher) -> None:
    """Tapping Save adds the whole batch and confirms the count and the deck it landed in."""
    # Arrange
    session = RecordingSession()

    # Act
    await send_snippet(dispatcher, session, LONG_TEXT, chat_id=2, user_id=2)
    await tap_action(dispatcher, session, "save", chat_id=2, user_id=2)

    # Assert
    assert session.last_edit == "Added 2 cards to Default."


async def test_user_can_send_a_short_snippet_through_the_command(dispatcher: Dispatcher) -> None:
    """/snippet opens a waiting state where even word-length text is treated as a snippet."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/snippet", chat_id=3, user_id=3)
    await send_snippet(dispatcher, session, "GIL", chat_id=3, user_id=3)

    # Assert
    assert session.answers[0] == "Send a text snippet or a screenshot to make cards from."
    assert session.last_answer == EXPECTED_PREVIEW


async def test_user_cannot_feed_the_waiting_state_an_unusable_message(dispatcher: Dispatcher) -> None:
    """Whitespace after /snippet is re-asked, not silently dropped or turned into a lookup."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/snippet", chat_id=4, user_id=4)
    await send(dispatcher, session, "   ", chat_id=4, user_id=4)

    # Assert
    assert session.last_answer == "That doesn't look like a snippet. Send a text snippet or a screenshot."


async def test_user_can_generate_cards_from_a_photo(dispatcher: Dispatcher) -> None:
    """A screenshot is downloaded and produces the same preview a text snippet does."""
    # Arrange
    session = RecordingSession()

    # Act
    await send_photo(dispatcher, session, caption="focus on the definition", chat_id=5, user_id=5)

    # Assert
    assert session.last_answer == EXPECTED_PREVIEW


async def test_user_can_regenerate_and_then_save(dispatcher: Dispatcher) -> None:
    """Regenerate replaces the preview with a fresh, still-savable batch."""
    # Arrange
    session = RecordingSession()

    # Act
    await send_snippet(dispatcher, session, LONG_TEXT, chat_id=6, user_id=6)
    await tap_action(dispatcher, session, "regenerate", chat_id=6, user_id=6, preview_message_id=301)
    await tap_action(dispatcher, session, "save", chat_id=6, user_id=6)

    # Assert
    assert session.answers.count(EXPECTED_PREVIEW) == 2
    assert session.last_edit == "Added 2 cards to Default."


async def test_user_can_regenerate_from_a_photo(dispatcher: Dispatcher) -> None:
    """Regenerate on a photo preview re-downloads the image by file_id instead of failing."""
    # Arrange
    session = RecordingSession()

    # Act
    await send_photo(dispatcher, session, chat_id=7, user_id=7)
    queue_file_download(session, b"fake-jpeg-bytes")
    await tap_action(dispatcher, session, "regenerate", chat_id=7, user_id=7, preview_message_id=302)
    await tap_action(dispatcher, session, "save", chat_id=7, user_id=7)

    # Assert
    assert session.answers.count(EXPECTED_PREVIEW) == 2
    assert session.last_edit == "Added 2 cards to Default."


async def test_user_can_cancel_the_preview(dispatcher: Dispatcher) -> None:
    """Cancel drops the preview and clears the pending state."""
    # Arrange
    bot = make_bot(RecordingSession())
    session = RecordingSession()

    # Act
    await send_snippet(dispatcher, session, LONG_TEXT, chat_id=8, user_id=8)
    await tap_action(dispatcher, session, "cancel", chat_id=8, user_id=8)

    # Assert
    assert session.last_edit == "Cancelled."
    context = dispatcher.fsm.resolve_context(bot, chat_id=8, user_id=8)
    assert context is not None
    assert await context.get_state() is None


async def test_short_word_is_still_a_vocabulary_lookup(dispatcher: Dispatcher) -> None:
    """A word-length message keeps producing a vocabulary card, not snippet cards — the routing split."""
    # Arrange
    session = RecordingSession()

    # Act
    await send_snippet(dispatcher, session, "serendipity", chat_id=9, user_id=9)

    # Assert
    assert session.last_answer == (
        "Add to English Words V2?\n\nWord: serendipity\nMeaning: a pleasant surprise\nExample: What a serendipity!"
    )


async def test_user_cannot_get_cards_from_an_uninstructive_snippet(
    dispatcher: Dispatcher, snippet_cards_generator: FakeSnippetCardsGenerator
) -> None:
    """A snippet the generator finds nothing in is answered explicitly, not with silence."""
    # Arrange
    session = RecordingSession()
    snippet_cards_generator.cards = []

    # Act
    await send(dispatcher, session, LONG_TEXT, chat_id=10, user_id=10)

    # Assert
    assert session.last_answer == "Couldn't find anything card-worthy in that snippet. Try a different passage."


async def test_user_cannot_generate_cards_when_the_generator_is_unavailable(
    dispatcher: Dispatcher, snippet_cards_generator: FakeSnippetCardsGenerator
) -> None:
    """A generator that can't be reached tells the user to retry later, not a generic error."""
    # Arrange
    session = RecordingSession()
    snippet_cards_generator.error = CardGenerationUnavailableError()

    # Act
    await send(dispatcher, session, LONG_TEXT, chat_id=11, user_id=11)

    # Assert
    assert session.last_answer == "The card generator is unavailable. Please try again later."


async def test_user_cannot_generate_cards_from_a_one_sided_batch(
    dispatcher: Dispatcher, snippet_cards_generator: FakeSnippetCardsGenerator
) -> None:
    """A generator that returns a card with a blank side produces a retry reply, not a broken preview."""
    # Arrange
    session = RecordingSession()
    snippet_cards_generator.cards = [DraftCard(front="Q", back="   ")]

    # Act
    await send(dispatcher, session, LONG_TEXT, chat_id=12, user_id=12)

    # Assert
    assert session.last_answer == "Couldn't generate cards from that snippet. Try again, or send a different passage."


async def test_user_cannot_generate_cards_without_authenticating(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway
) -> None:
    """A session-expired failure tells the user to authenticate — before any tokens are spent."""
    # Arrange
    session = RecordingSession()
    card_gateway.error = AnkiSessionExpiredError()

    # Act
    await send(dispatcher, session, LONG_TEXT, chat_id=13, user_id=13)

    # Assert
    assert session.last_answer == "Run /auth first."


async def test_user_cannot_generate_cards_for_a_notetype_without_two_fields(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway
) -> None:
    """A notetype that isn't front/back-shaped is named to the user before generation starts."""
    # Arrange
    session = RecordingSession()
    card_gateway.field_count = 8

    # Act
    await send(dispatcher, session, LONG_TEXT, chat_id=14, user_id=14)

    # Assert
    assert session.last_answer == (
        "AnkiWeb's current notetype isn't set up for a simple front/back card. "
        "Switch to a two-field notetype (e.g. Basic) in AnkiWeb's editor and try again."
    )


async def test_user_can_see_exactly_what_was_saved_when_ankiweb_fails_midway(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway
) -> None:
    """A batch AnkiWeb accepts only part of is reported as 'saved K of N', never as all-or-nothing."""
    # Arrange
    session = RecordingSession()
    await send_snippet(dispatcher, session, LONG_TEXT, chat_id=15, user_id=15)
    card_gateway.fail_add_after = 1

    # Act
    await tap_action(dispatcher, session, "save", chat_id=15, user_id=15)

    # Assert
    assert session.last_edit == (
        "Saved 1 of 2 cards to Default, then AnkiWeb failed. Resend the snippet to add the rest."
    )


async def test_user_cannot_save_anything_when_ankiweb_fails_at_the_first_card(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway
) -> None:
    """A batch that fails before any card is in reads as a plain failure, not a confusing 'saved 0 of N'."""
    # Arrange
    session = RecordingSession()
    await send_snippet(dispatcher, session, LONG_TEXT, chat_id=16, user_id=16)
    card_gateway.fail_add_after = 0

    # Act
    await tap_action(dispatcher, session, "save", chat_id=16, user_id=16)

    # Assert
    assert session.last_edit == "Failed to add the cards to AnkiWeb. Please try again later."


async def test_user_cannot_save_when_the_session_has_expired(
    dispatcher: Dispatcher, card_gateway: FakeCardGateway
) -> None:
    """A session that expires between preview and Save tells the user to authenticate."""
    # Arrange
    session = RecordingSession()
    await send_snippet(dispatcher, session, LONG_TEXT, chat_id=17, user_id=17)
    card_gateway.error = AnkiSessionExpiredError()

    # Act
    await tap_action(dispatcher, session, "save", chat_id=17, user_id=17)

    # Assert
    assert session.last_edit == "Run /auth first."
