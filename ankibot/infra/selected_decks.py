from typing import override

from ankibot.application.common.selected_deck_store import SelectedDeckStore


class InMemorySelectedDeckStore(SelectedDeckStore):
    """Keeps each user's deck choice in process memory.

    The selection is lost on restart, after which the bot falls back to AnkiWeb's current deck.
    """

    def __init__(self) -> None:
        self._decks: dict[int, int] = {}

    @override
    async def get(self, user_id: int) -> int | None:
        return self._decks.get(user_id)

    @override
    async def set(self, user_id: int, deck_id: int) -> None:
        self._decks[user_id] = deck_id
