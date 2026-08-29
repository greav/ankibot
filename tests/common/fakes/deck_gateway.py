"""In-memory implementation of the DeckGateway port."""

from typing import override

from ankibot.application.manage_decks import Deck
from ankibot.application.manage_decks.ports import DeckGateway


class FakeDeckGateway(DeckGateway):
    """Lists decks without leaving the process, or raises ``error`` instead when one is set.

    ``decks``/``error`` stay writable so a test sharing one dispatcher can steer its own run.
    """

    def __init__(self, decks: list[Deck] | None = None, error: Exception | None = None) -> None:
        self.decks = decks if decks is not None else []
        self.error = error

    @override
    async def list_decks(self) -> list[Deck]:
        """Raise the configured error, or return ``decks`` when there is none."""
        if self.error is not None:
            raise self.error
        return list(self.decks)
