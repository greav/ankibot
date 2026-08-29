"""In-memory implementation of the SelectedDeckStore port."""

from typing import override

from ankibot.application.common.selected_deck_store import SelectedDeckStore


class FakeSelectedDeckStore(SelectedDeckStore):
    """Remembers deck choices in a public dict the reset fixture can clear.

    The production ``InMemorySelectedDeckStore`` has no reset hook, and adding one purely for tests
    would put test-only API in production code.
    """

    def __init__(self) -> None:
        self.decks: dict[int, int] = {}

    @override
    async def get(self, user_id: int) -> int | None:
        return self.decks.get(user_id)

    @override
    async def set(self, user_id: int, deck_id: int) -> None:
        self.decks[user_id] = deck_id
