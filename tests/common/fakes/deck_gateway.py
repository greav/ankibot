"""In-memory implementation of the DeckGateway port."""

from typing import override

from ankibot.application.manage_decks import Deck
from ankibot.application.manage_decks.ports import DeckGateway


class FakeDeckGateway(DeckGateway):
    """Keeps the account's decks in a list, or raises ``error`` on every call while one is set.

    ``decks``/``error`` stay writable so a test sharing one dispatcher can steer its own run. A
    created deck gets the next free id, the way a fresh AnkiWeb deck gets a new one, so a test can
    read it back through ``/decks`` rather than through the fake.
    """

    def __init__(self, decks: list[Deck] | None = None, error: Exception | None = None) -> None:
        self.decks = decks if decks is not None else []
        self.error = error

    @override
    async def list_decks(self) -> list[Deck]:
        """Raise the configured error, or return ``decks`` when there is none."""
        self._raise_if_failing()
        return list(self.decks)

    @override
    async def create_deck(self, name: str) -> None:
        self._raise_if_failing()
        if any(deck.name.casefold() == name.casefold() for deck in self.decks):
            return  # AnkiWeb treats a duplicate as a no-op.
        next_id = max((deck.id for deck in self.decks), default=0) + 1
        self.decks.append(Deck(id=next_id, name=name))

    @override
    async def remove_deck(self, deck_id: int) -> None:
        self._raise_if_failing()
        self.decks = [deck for deck in self.decks if deck.id != deck_id]

    def _raise_if_failing(self) -> None:
        if self.error is not None:
            raise self.error
