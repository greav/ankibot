import logging
from abc import abstractmethod
from typing import Protocol

from ankibot.application.exceptions.decks import NoDeckSelectedError

logger = logging.getLogger(__name__)


class SelectedDeckStore(Protocol):
    """Remembers which deck a Telegram user sends new cards to."""

    @abstractmethod
    async def get_deck(self, user_id: int) -> int | None:
        """Return the deck the user picked, or None when they have not picked one."""
        raise NotImplementedError

    @abstractmethod
    async def set_deck(self, user_id: int, deck_id: int) -> None:
        """Remember ``deck_id`` as the user's target deck."""
        raise NotImplementedError

    @abstractmethod
    async def clear_deck(self, user_id: int) -> None:
        """Forget the user's target deck, so the next card asks for one; a no-op when none is set."""
        raise NotImplementedError


async def chosen_deck(store: SelectedDeckStore, user_id: int) -> int:
    """The deck ``user_id`` picked, or ``NoDeckSelectedError`` when they have not picked one.

    Shared by every interactor that writes a card: none of them guesses a deck. Falling back to
    AnkiWeb's current deck sent cards to the hidden built-in deck without anyone noticing.
    """
    deck_id = await store.get_deck(user_id)
    if deck_id is None:
        logger.info("User %s has not chosen a deck yet", user_id)
        raise NoDeckSelectedError
    return deck_id
