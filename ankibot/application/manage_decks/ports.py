from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, kw_only=True)
class Deck:
    """One AnkiWeb deck, as far as picking a target for new cards needs to know it."""

    id: int
    name: str


class DeckGateway(Protocol):
    """Reads and edits the decks the AnkiWeb account owns."""

    @abstractmethod
    async def list_decks(self) -> list[Deck]:
        """Return every deck, or raise ``AnkiSessionExpiredError``/``AnkiDeckListingError``."""
        raise NotImplementedError

    @abstractmethod
    async def create_deck(self, name: str) -> None:
        """Create a deck called ``name``, or raise ``AnkiSessionExpiredError``/``AnkiDeckCreationError``.

        AnkiWeb reports nothing about the new deck, not even its id: a caller that needs it lists
        the decks again. A name containing ``::`` creates a nested deck, as it does in Anki.
        """
        raise NotImplementedError

    @abstractmethod
    async def remove_deck(self, deck_id: int) -> None:
        """Delete the deck and every card in it, or raise ``AnkiSessionExpiredError``/``AnkiDeckRemovalError``."""
        raise NotImplementedError
