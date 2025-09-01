from abc import abstractmethod
from typing import Protocol

from httpx import Cookies

from .models import CardGenerationRequest, CardGenerationResponse


class CookieStorage(Protocol):
    """Protocol for storing and retrieving HTTP cookies."""

    @abstractmethod
    async def store_cookies(self, key: str, cookies: Cookies) -> None:
        """Store cookies for a given key."""
        ...

    @abstractmethod
    async def get_cookies(self, key: str) -> Cookies | None:
        """Retrieve cookies for a given key. Returns None if not found."""
        ...

    @abstractmethod
    async def clear_cookies(self, key: str) -> None:
        """Clear cookies for a given key."""
        ...


class AnkiApiClient(Protocol):
    """Protocol for Anki API operations."""

    @abstractmethod
    async def authenticate(self, username: str, password: str) -> bool:
        """Authenticate with Anki web service. Returns True if successful."""
        ...

    @abstractmethod
    async def get_decks_info(self) -> list[dict]:
        """Get information about available decks."""
        ...

    @abstractmethod
    async def get_info_for_adding(self) -> dict:
        """Get information needed for adding cards (note types, fields, etc.)."""
        ...

    @abstractmethod
    async def add_card(self, front: str, back: str, deck_id: int, notetype_id: int, tags: str = "") -> bool:
        """Add a new card to the specified deck. Returns True if successful."""
        ...


class OpenAIClient(Protocol):
    """Protocol for OpenAI API operations."""

    @abstractmethod
    async def generate_cards_from_passage(self, request: CardGenerationRequest) -> CardGenerationResponse:
        """Generate Anki cards from a text passage using structured output."""
        ...
