from abc import abstractmethod
from typing import Protocol


class SelectedDeckStore(Protocol):
    """Remembers which deck a Telegram user sends new cards to."""

    @abstractmethod
    async def get(self, user_id: int) -> int | None:
        """Return the deck the user picked, or None when they have not picked one."""
        raise NotImplementedError

    @abstractmethod
    async def set(self, user_id: int, deck_id: int) -> None:
        """Remember ``deck_id`` as the user's target deck."""
        raise NotImplementedError
