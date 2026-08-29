from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, kw_only=True)
class Deck:
    """One AnkiWeb deck, as far as picking a target for new cards needs to know it."""

    id: int
    name: str


class DeckGateway(Protocol):
    """Reads the decks the AnkiWeb account owns."""

    @abstractmethod
    async def list_decks(self) -> list[Deck]:
        """Return every deck, or raise ``AnkiSessionExpiredError``/``AnkiDeckListingError``."""
        raise NotImplementedError
