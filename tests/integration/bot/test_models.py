"""The /model outcomes, driven through the composed dispatcher rather than by calling handlers.

Going through ``feed_update`` covers the ``Command("model")`` filter, the callback-data filter,
router order and dishka's injection of interactors and the user id on top of the handler bodies.
"""

from aiogram import Dispatcher
from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardMarkup, Update

from ankibot.presentation.keyboards.models import ModelCallback
from tests.common.fakes.selected_model_store import FakeSelectedModelStore
from tests.common.telegram import RecordingSession, make_bot, make_callback_query, make_message

USER_ID = 12
CHAT_ID = 12


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


def button_labels(session: RecordingSession) -> list[str]:
    """The text of every button on the keyboard the bot last sent."""
    message = next(request for request in reversed(session.requests) if isinstance(request, SendMessage))
    assert isinstance(message.reply_markup, InlineKeyboardMarkup)
    return [button.text for row in message.reply_markup.inline_keyboard for button in row]


async def test_user_can_see_the_default_model_marked_before_picking_one(dispatcher: Dispatcher) -> None:
    """/model offers one button per model, marking the default when the user has not picked yet."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/model")

    # Assert
    assert session.last_answer == "Choose a model:"
    assert button_labels(session) == ["✓ GPT-4o mini", "GPT-5 mini"]


async def test_user_can_see_their_own_model_marked(
    dispatcher: Dispatcher, selected_models: FakeSelectedModelStore
) -> None:
    """Once picked, the mark follows the user's choice rather than the default."""
    # Arrange
    selected_models.models[USER_ID] = "gpt-5-mini"
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/model")

    # Assert
    assert button_labels(session) == ["GPT-4o mini", "✓ GPT-5 mini"]


async def test_user_can_select_a_model(dispatcher: Dispatcher, selected_models: FakeSelectedModelStore) -> None:
    """Tapping a model confirms it by label and remembers its id for the user's next card."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/model")
    await tap(dispatcher, session, ModelCallback(id="gpt-5-mini").pack())

    # Assert
    assert session.last_edit == "Model set to GPT-5 mini."
    assert selected_models.models[USER_ID] == "gpt-5-mini"


async def test_user_cannot_select_a_model_outside_the_catalog(
    dispatcher: Dispatcher, selected_models: FakeSelectedModelStore
) -> None:
    """A model dropped from the catalog since the keyboard was rendered is refused, not remembered."""
    # Arrange
    session = RecordingSession()

    # Act
    await send(dispatcher, session, "/model")
    await tap(dispatcher, session, ModelCallback(id="gpt-3.5-turbo").pack())

    # Assert
    assert session.last_edit == "That model is no longer offered. Run /model again."
    assert USER_ID not in selected_models.models


async def test_user_cannot_use_model_from_a_chat_that_hides_who_they_are(
    dispatcher: Dispatcher, selected_models: FakeSelectedModelStore
) -> None:
    """A senderless update is told so, and leaves no model choice behind for the next one to inherit."""
    # Arrange — a channel post and an anonymous group admin both arrive without a ``from_user``.
    session = RecordingSession()
    bot = make_bot(session)
    update = Update(update_id=1, message=make_message(bot, text="/model", chat_id=CHAT_ID, user_id=None))

    # Act
    await dispatcher.feed_update(bot, update)

    # Assert
    assert (
        session.last_answer
        == "I can't tell who you are here. Send the command from your own account in a private chat."
    )
    assert selected_models.models == {}
