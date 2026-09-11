"""The deck picker's shared controller vocabulary: its replies and the steps both flows take.

Router-free on purpose, for the same reason ``keyboards/`` is: ``/decks`` and ``/addcard`` both
open this picker, and a module owning a ``Router`` cannot be imported by another handler module.
Keeping these here also keeps the two commands from drifting into two wordings of one reply.
"""

import logging
from collections.abc import Callable

from aiogram.types import CallbackQuery, Message

from ankibot.application.exceptions.anki import AnkiDeckNotFoundError, AnkiSessionExpiredError
from ankibot.application.exceptions.base import ApplicationError
from ankibot.application.manage_decks import SelectDeck, SelectDeckRequest
from ankibot.presentation.identity import TelegramUserId

logger = logging.getLogger(__name__)

CHOOSE_A_DECK = "Choose a deck:"
NO_DECKS = "You have no decks in AnkiWeb yet."
AUTH_FIRST = "Run /auth first."
DECK_GONE = "That deck no longer exists in AnkiWeb. Run /decks again."
CHOOSE_DECK_FIRST = "Choose a deck with /decks first."
ANKIWEB_UNREACHABLE = "Failed to reach AnkiWeb. Please try again later."


def deck_list_error_reply(error: ApplicationError) -> str:
    """The reply for a failure to read the deck list, shared by both entry points."""
    if isinstance(error, AnkiSessionExpiredError):
        return AUTH_FIRST
    logger.warning("Failed to list AnkiWeb decks: %s", error)
    return ANKIWEB_UNREACHABLE


async def edit_into(callback: CallbackQuery, text: str) -> None:
    """Edit the picker message into ``text``, dropping the keyboard.

    aiogram types ``callback.message`` as ``Message | InaccessibleMessage | None``; only a real
    ``Message`` can be edited, and an inaccessible one is simply too old to touch. The result is
    discarded, so nothing reads a Telegram reply back.
    """
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)


async def select_tapped_deck(
    callback: CallbackQuery,
    user_id: TelegramUserId,
    deck_id: int,
    select_deck: SelectDeck,
    confirmation: Callable[[str], str],
) -> str | None:
    """Store the tapped deck and edit the picker into its outcome; the deck's name once it is stored.

    ``/addcard`` needs the outcome to decide whether to advance its FSM, the snippet preview
    needs the name to re-address itself; ``/decks`` ignores both.
    """
    stored: str | None = None
    try:
        result = await select_deck.execute(SelectDeckRequest(user_id=user_id, deck_id=deck_id))
    except AnkiSessionExpiredError:
        await edit_into(callback, AUTH_FIRST)
    except AnkiDeckNotFoundError:
        await edit_into(callback, DECK_GONE)
    except ApplicationError as error:
        logger.warning("Failed to select an AnkiWeb deck: %s", error)
        await edit_into(callback, ANKIWEB_UNREACHABLE)
    else:
        await edit_into(callback, confirmation(result.deck_name))
        stored = result.deck_name

    await callback.answer()
    return stored
