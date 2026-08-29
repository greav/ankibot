"""In-memory implementation of the CardGateway port."""

from typing import override

from ankibot.application.exceptions.anki import AnkiDeckNotFoundError
from ankibot.application.manage_cards.create_card import AddTarget, CardGateway, CreateCardRequest


class FakeCardGateway(CardGateway):
    """Adds cards without leaving the process, or raises ``error`` instead when one is set.

    It holds the deck list itself rather than a ready-made ``AddTarget``, so which deck a card
    landed in is observable in the reply the handler sends. Every field stays writable so a test
    sharing one dispatcher can steer the run it is about to make.
    """

    def __init__(
        self,
        *,
        decks: dict[int, str],
        current_deck_id: int,
        notetype_id: int = 1,
        field_count: int = 2,
        error: Exception | None = None,
    ) -> None:
        self.decks = decks
        self.current_deck_id = current_deck_id
        self.notetype_id = notetype_id
        self.field_count = field_count
        self.error = error

    @override
    async def add_target(self, deck_id: int | None) -> AddTarget:
        """Raise the configured error, or resolve ``deck_id`` against the fake's deck list."""
        if self.error is not None:
            raise self.error

        if deck_id is None:
            return AddTarget(
                deck_id=self.current_deck_id,
                notetype_id=self.notetype_id,
                deck_name=self.decks[self.current_deck_id],
                field_count=self.field_count,
            )

        name = self.decks.get(deck_id)
        if name is None:
            raise AnkiDeckNotFoundError

        return AddTarget(
            deck_id=deck_id,
            notetype_id=self.notetype_id,
            deck_name=name,
            field_count=self.field_count,
        )

    @override
    async def add_card(self, target: AddTarget, request: CreateCardRequest) -> None:
        """Raise the configured error, or succeed silently when there is none."""
        if self.error is not None:
            raise self.error
