from __future__ import annotations

from typing import Protocol

from .models import AddNotePayload, CardTemplate, EditorInfo, GeneratedCard


class CardGenerator(Protocol):
    async def generate_card(self, word: str, template: CardTemplate) -> GeneratedCard:
        """Create a fully populated card for the provided word."""


class AnkiWebGateway(Protocol):
    async def get_default_deck_id(self) -> int:
        """Return the ID of the user's current default deck."""

    async def get_editor_info(self) -> EditorInfo:
        """Return data describing the current notetype fields."""

    async def add_note(self, payload: AddNotePayload) -> int:
        """Persist the provided note and return its ID."""
