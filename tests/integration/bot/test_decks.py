"""The /decks outcomes, driven through the composed dispatcher rather than by calling handlers.

Going through ``feed_update`` covers the ``Command("decks")`` filter, the callback-data filters,
router order and dishka's injection of interactors and the user id on top of the handler bodies.
"""

import logging

import pytest
from aiogram import Dispatcher
from aiogram.methods import EditMessageText, SendMessage
from aiogram.types import InlineKeyboardMarkup, Update

from ankibot.application.exceptions.anki import (
    AnkiDeckCreationError,
    AnkiDeckListingError,
    AnkiDeckRemovalError,
    AnkiSessionExpiredError,
)
from ankibot.application.manage_decks import Deck
from ankibot.presentation.keyboards.decks import (
    ConfirmRemoveDeckCallback,
    DeckCallback,
    DeckPageCallback,
    NewDeckCallback,
    PickerMode,
    RemoveDeckCallback,
)
from tests.common.fakes.deck_gateway import FakeDeckGateway
from tests.common.fakes.selected_deck_store import FakeSelectedDeckStore
from tests.common.telegram import RecordingSession, make_bot, make_callback_query, make_message

USER_ID = 11
CHAT_ID = 11


async def send(dispatcher: Dispatcher, session: RecordingSession, text: str) -> None:
    """Feed one message to the dispatcher, replies landing in ``session``."""
    bot = make_bot(session)
    update = Update(update_id=1, message=make_message(bot, text=text, chat_id=CHAT_ID, user_id=USER_ID))
    await dispatcher.feed_update(bot, update)


async def tap(dispatcher: Dispatcher, session: RecordingSession, data: str) -> None:
    """Feed one inline-button tap to the dispatcher, replies landing in ``session``."""
    bot = make_bot(session)
    callback = make_callback_query(bot, data, chat_id=CHAT_ID, user_id=USER_ID)
    await dispatcher.feed_update(bot, Update(update_id=2, callback_query=callback))


def edited_labels(session: RecordingSession) -> list[str]:
    """The text of every button on the keyboard the bot last edited a message into."""
    edit = next(request for request in reversed(session.requests) if isinstance(request, EditMessageText))
    assert isinstance(edit.reply_markup, InlineKeyboardMarkup)
    return [button.text for row in edit.reply_markup.inline_keyboard for button in row]


async def enter_delete_mode(dispatcher: Dispatcher, session: RecordingSession) -> None:
    """Open /decks and tap its "➖ Delete deck" row."""
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, DeckPageCallback(page=0, mode=PickerMode.DELETE).pack())


def button_labels(session: RecordingSession) -> list[str]:
    """The text of every button on the keyboard the bot last sent."""
    message = next(request for request in reversed(session.requests) if isinstance(request, SendMessage))
    assert isinstance(message.reply_markup, InlineKeyboardMarkup)
    return [button.text for row in message.reply_markup.inline_keyboard for button in row]


async def test_user_can_see_their_decks(dispatcher: Dispatcher, selected_decks: FakeSelectedDeckStore) -> None:
    """/decks offers one button per deck, marking the picked one, plus rows to create a deck and to delete one."""
    # Arrange
    selected_decks.decks[USER_ID] = 2
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")

    # Assert
    assert session.last_answer == "Choose a deck:"
    assert button_labels(session) == ["Default", "✓ Spanish", "➕ New deck", "➖ Delete deck"]


async def test_user_can_see_that_they_have_no_decks(dispatcher: Dispatcher, deck_gateway: FakeDeckGateway) -> None:
    """An account with no decks gets told so, offered a way to create the first one, and nothing to delete."""
    # Arrange
    deck_gateway.decks = []
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")

    # Assert
    assert session.last_answer == "You have no decks in AnkiWeb yet."
    assert button_labels(session) == ["➕ New deck"]


async def test_user_can_select_a_deck(dispatcher: Dispatcher, selected_decks: FakeSelectedDeckStore) -> None:
    """Tapping a deck confirms it by name and remembers it for the user's next card."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, DeckCallback(id=2).pack())

    # Assert
    assert session.last_edit == "Deck set to Spanish."
    assert selected_decks.decks[USER_ID] == 2


async def test_user_can_page_through_a_long_deck_list(dispatcher: Dispatcher, deck_gateway: FakeDeckGateway) -> None:
    """A list longer than one page pages forward to the decks the first page could not show."""
    # Arrange
    deck_gateway.decks = [Deck(id=index, name=f"deck-{index}") for index in range(20)]
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, DeckPageCallback(page=1).pack())

    # Assert
    assert edited_labels(session)[:8] == [f"deck-{index}" for index in range(8, 16)]


async def test_user_cannot_see_decks_without_authenticating(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway
) -> None:
    """A session-expired failure tells the user to authenticate, not a generic error."""
    # Arrange
    deck_gateway.error = AnkiSessionExpiredError()
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")

    # Assert
    assert session.last_answer == "Run /auth first."


async def test_user_cannot_see_decks_when_ankiweb_fails(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway, caplog: pytest.LogCaptureFixture
) -> None:
    """Any other AnkiWeb failure produces the generic retry message, with the reason only in the log."""
    # Arrange
    deck_gateway.error = AnkiDeckListingError("distinctive-boom-reason")
    session = RecordingSession()

    # Act
    with caplog.at_level(logging.WARNING):
        await send(dispatcher, session, "/decks")

    # Assert
    assert session.last_answer == "Failed to reach AnkiWeb. Please try again later."
    assert "distinctive-boom-reason" in caplog.text


async def test_user_cannot_select_a_deck_that_no_longer_exists(
    dispatcher: Dispatcher, selected_decks: FakeSelectedDeckStore
) -> None:
    """A deck deleted since the keyboard was rendered is refused instead of silently remembered."""
    # Arrange
    selected_decks.decks.pop(USER_ID)
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, DeckCallback(id=999).pack())

    # Assert
    assert session.last_edit == "That deck no longer exists in AnkiWeb. Run /decks again."
    assert USER_ID not in selected_decks.decks


async def test_user_cannot_use_a_command_from_a_chat_that_hides_who_they_are(
    dispatcher: Dispatcher,
    selected_decks: FakeSelectedDeckStore,
) -> None:
    """A senderless update is told so, and leaves no deck choice behind for the next one to inherit.

    The user id is resolved as a dependency, so the refusal happens before the handler body runs and
    only the errors router can answer — which is the guarantee no unit test reaches.
    """
    # Arrange — a channel post and an anonymous group admin both arrive without a ``from_user``.
    choices_before = dict(selected_decks.decks)
    session = RecordingSession()
    bot = make_bot(session)
    update = Update(update_id=1, message=make_message(bot, text="/decks", chat_id=CHAT_ID, user_id=None))

    # Act
    await dispatcher.feed_update(bot, update)

    # Assert
    assert (
        session.last_answer
        == "I can't tell who you are here. Send the command from your own account in a private chat."
    )
    assert selected_decks.decks == choices_before


async def test_user_can_create_a_deck(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway, selected_decks: FakeSelectedDeckStore
) -> None:
    """A name typed after "New deck" becomes a deck in AnkiWeb, and the user's next cards go there."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, NewDeckCallback().pack())
    await send(dispatcher, session, "Italian")

    # Assert
    assert session.last_edit == "Send the name of the new deck, or /cancel."
    assert session.last_answer == "Deck Italian created. New cards go there now."
    created = next(deck for deck in deck_gateway.decks if deck.name == "Italian")
    assert selected_decks.decks[USER_ID] == created.id


async def test_user_can_see_a_created_deck_in_the_picker(dispatcher: Dispatcher) -> None:
    """The next /decks lists the new deck, already marked as the target."""
    # Arrange
    session = RecordingSession()
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, NewDeckCallback().pack())
    await send(dispatcher, session, "Italian")

    # Act
    await send(dispatcher, session, "/decks")

    # Assert
    assert "✓ Italian" in button_labels(session)


async def test_user_can_retype_a_blank_deck_name(dispatcher: Dispatcher) -> None:
    """A blank name is refused without ending the prompt, so the next message still names the deck."""
    # Arrange
    session = RecordingSession()
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, NewDeckCallback().pack())

    # Act
    await send(dispatcher, session, "   ")
    refusal = session.last_answer
    await send(dispatcher, session, "Italian")

    # Assert
    assert refusal == "A deck name can't be empty. Send the name of the new deck, or /cancel."
    assert session.last_answer == "Deck Italian created. New cards go there now."


async def test_user_cannot_create_a_deck_named_after_a_command(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway
) -> None:
    """A mistyped command sent as the name is refused instead of becoming a deck called "/word"."""
    # Arrange
    session = RecordingSession()
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, NewDeckCallback().pack())

    # Act
    await send(dispatcher, session, "/word")

    # Assert
    assert session.last_answer == "A deck name can't be empty. Send the name of the new deck, or /cancel."
    assert all(deck.name != "/word" for deck in deck_gateway.decks)


async def test_user_cannot_create_a_deck_that_already_exists(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway
) -> None:
    """A name already taken, in any letter case, is reported rather than silently reused."""
    # Arrange
    session = RecordingSession()
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, NewDeckCallback().pack())

    # Act
    await send(dispatcher, session, "spanish")

    # Assert
    assert session.last_answer == "You already have a deck named Spanish."
    assert [deck.name for deck in deck_gateway.decks] == ["Default", "Spanish"]


async def test_user_can_cancel_creating_a_deck(dispatcher: Dispatcher, deck_gateway: FakeDeckGateway) -> None:
    """/cancel ends the prompt, so the next message is no longer taken for a deck name.

    It is instead picked up by the vocabulary-word catch-all (see test_vocabulary_card.py), which is
    the guarantee this test states; a real ``sendMessage`` reply is queued so that flow's own read
    of its preview's message id does not fail this test.
    """
    # Arrange
    session = RecordingSession()
    session.queue_response(SendMessage, make_message(make_bot(session), message_id=999, chat_id=CHAT_ID))
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, NewDeckCallback().pack())

    # Act
    await send(dispatcher, session, "/cancel")
    await send(dispatcher, session, "Italian")

    # Assert
    assert session.answers[:2] == ["Choose a deck:", "Cancelled."]
    assert all(deck.name != "Italian" for deck in deck_gateway.decks)


async def test_user_can_reopen_the_picker_instead_of_naming_a_deck(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway
) -> None:
    """/decks sent at the name prompt abandons it, so a plain message afterwards creates no deck.

    The message goes to the vocabulary-word catch-all instead, as in the /cancel test above.
    """
    # Arrange
    session = RecordingSession()
    session.queue_response(SendMessage, make_message(make_bot(session), message_id=999, chat_id=CHAT_ID))
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, NewDeckCallback().pack())

    # Act
    await send(dispatcher, session, "/decks")
    await send(dispatcher, session, "Italian")

    # Assert
    assert session.answers[:2] == ["Choose a deck:", "Choose a deck:"]
    assert all(deck.name != "Italian" for deck in deck_gateway.decks)


async def test_user_cannot_create_a_deck_without_authenticating(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway
) -> None:
    """A session that expired between the prompt and the name tells the user to authenticate."""
    # Arrange
    session = RecordingSession()
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, NewDeckCallback().pack())
    deck_gateway.error = AnkiSessionExpiredError()

    # Act
    await send(dispatcher, session, "Italian")

    # Assert
    assert session.last_answer == "Run /auth first."


async def test_user_cannot_create_a_deck_when_ankiweb_fails(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway, caplog: pytest.LogCaptureFixture
) -> None:
    """Any other failure gets the generic retry message, with the reason only in the log."""
    # Arrange
    session = RecordingSession()
    await send(dispatcher, session, "/decks")
    await tap(dispatcher, session, NewDeckCallback().pack())
    deck_gateway.error = AnkiDeckCreationError("distinctive-create-reason")

    # Act
    with caplog.at_level(logging.WARNING):
        await send(dispatcher, session, "Italian")

    # Assert
    assert session.last_answer == "Failed to create the deck in AnkiWeb. Please try again later."
    assert "distinctive-create-reason" in caplog.text


async def test_user_can_delete_a_deck(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway, selected_decks: FakeSelectedDeckStore
) -> None:
    """Deleting asks first, names the deck, and on confirmation removes it while another target stays."""
    # Arrange
    session = RecordingSession()

    # Act
    await enter_delete_mode(dispatcher, session)
    await tap(dispatcher, session, RemoveDeckCallback(id=2, page=0).pack())
    prompt = session.last_edit
    await tap(dispatcher, session, ConfirmRemoveDeckCallback(id=2).pack())

    # Assert
    assert prompt == "Delete Spanish and every card in it?"
    assert session.last_edit == "Deck Spanish deleted."
    assert [deck.name for deck in deck_gateway.decks] == ["Default"]
    assert selected_decks.decks[USER_ID] == 1


async def test_user_can_delete_the_deck_their_cards_go_to(
    dispatcher: Dispatcher, selected_decks: FakeSelectedDeckStore
) -> None:
    """Deleting the target deck forgets the choice and says so, rather than aiming cards at a ghost."""
    # Arrange
    selected_decks.decks[USER_ID] = 2
    session = RecordingSession()

    # Act
    await enter_delete_mode(dispatcher, session)
    await tap(dispatcher, session, RemoveDeckCallback(id=2, page=0).pack())
    await tap(dispatcher, session, ConfirmRemoveDeckCallback(id=2).pack())

    # Assert
    assert session.last_edit == "Deck Spanish deleted. Choose where new cards go with /decks."
    assert USER_ID not in selected_decks.decks


async def test_user_can_enter_delete_mode(dispatcher: Dispatcher) -> None:
    """The delete row turns the list into one where a tap deletes, says so, and offers a way back."""
    # Arrange
    session = RecordingSession()

    # Act
    await enter_delete_mode(dispatcher, session)

    # Assert
    assert session.last_edit == "Choose a deck to delete:"
    assert edited_labels(session) == ["✓ Default", "Spanish", "◁ Back"]


async def test_user_can_leave_delete_mode(dispatcher: Dispatcher) -> None:
    """Back returns to the ordinary picker, where a tap selects again."""
    # Arrange
    session = RecordingSession()
    await enter_delete_mode(dispatcher, session)

    # Act
    await tap(dispatcher, session, DeckPageCallback(page=0, mode=PickerMode.MANAGE).pack())

    # Assert
    assert session.last_edit == "Choose a deck:"
    assert edited_labels(session) == ["✓ Default", "Spanish", "➕ New deck", "➖ Delete deck"]


async def test_user_can_back_out_of_deleting_a_deck(dispatcher: Dispatcher, deck_gateway: FakeDeckGateway) -> None:
    """Cancel on the confirmation returns to the delete list with every deck still in place."""
    # Arrange
    session = RecordingSession()
    await enter_delete_mode(dispatcher, session)
    await tap(dispatcher, session, RemoveDeckCallback(id=2, page=0).pack())

    # Act
    await tap(dispatcher, session, DeckPageCallback(page=0, mode=PickerMode.DELETE).pack())

    # Assert
    assert session.last_edit == "Choose a deck to delete:"
    assert edited_labels(session) == ["✓ Default", "Spanish", "◁ Back"]
    assert [deck.name for deck in deck_gateway.decks] == ["Default", "Spanish"]


async def test_user_cannot_delete_a_deck_that_no_longer_exists(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway
) -> None:
    """A delete button left over from a stale keyboard is refused, not confirmed."""
    # Arrange
    session = RecordingSession()
    await enter_delete_mode(dispatcher, session)
    deck_gateway.decks = [deck for deck in deck_gateway.decks if deck.id != 2]

    # Act
    await tap(dispatcher, session, RemoveDeckCallback(id=2, page=0).pack())

    # Assert
    assert session.last_edit == "That deck no longer exists in AnkiWeb. Run /decks again."


async def test_user_cannot_confirm_deleting_a_deck_that_no_longer_exists(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway
) -> None:
    """A deck gone between the prompt and the confirmation is reported gone, not deleted again."""
    # Arrange
    session = RecordingSession()
    await enter_delete_mode(dispatcher, session)
    await tap(dispatcher, session, RemoveDeckCallback(id=2, page=0).pack())
    deck_gateway.decks = [deck for deck in deck_gateway.decks if deck.id != 2]

    # Act
    await tap(dispatcher, session, ConfirmRemoveDeckCallback(id=2).pack())

    # Assert
    assert session.last_edit == "That deck no longer exists in AnkiWeb. Run /decks again."


async def test_user_cannot_delete_a_deck_without_authenticating(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway
) -> None:
    """A session that expired before the confirmation tells the user to authenticate."""
    # Arrange
    session = RecordingSession()
    await enter_delete_mode(dispatcher, session)
    await tap(dispatcher, session, RemoveDeckCallback(id=2, page=0).pack())
    deck_gateway.error = AnkiSessionExpiredError()

    # Act
    await tap(dispatcher, session, ConfirmRemoveDeckCallback(id=2).pack())

    # Assert
    assert session.last_edit == "Run /auth first."


async def test_user_cannot_delete_a_deck_when_ankiweb_fails(
    dispatcher: Dispatcher, deck_gateway: FakeDeckGateway, caplog: pytest.LogCaptureFixture
) -> None:
    """Any other failure gets the generic retry message, with the reason only in the log."""
    # Arrange
    session = RecordingSession()
    await enter_delete_mode(dispatcher, session)
    await tap(dispatcher, session, RemoveDeckCallback(id=2, page=0).pack())
    deck_gateway.error = AnkiDeckRemovalError("distinctive-remove-reason")

    # Act
    with caplog.at_level(logging.WARNING):
        await tap(dispatcher, session, ConfirmRemoveDeckCallback(id=2).pack())

    # Assert
    assert session.last_edit == "Failed to delete the deck in AnkiWeb. Please try again later."
    assert "distinctive-remove-reason" in caplog.text
