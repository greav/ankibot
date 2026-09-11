"""In-memory implementation of the CardGateway port."""

from typing import override

from ankibot.application.common.card_gateway import AddTarget, CardGateway
from ankibot.application.exceptions.anki import AnkiCardCreationError, AnkiDeckNotFoundError


class FakeCardGateway(CardGateway):
    """Adds cards without leaving the process, or raises ``error`` instead when one is set.

    It holds the deck list itself rather than a ready-made ``AddTarget``, so which deck a card
    landed in is observable in the reply the handler sends. Every field stays writable so a test
    sharing one dispatcher can steer the run it is about to make. ``fail_add_after`` makes a batch
    fail partway: that many ``add_card`` calls succeed, then one raises — the shape a partial-save
    reply is about.
    """

    def __init__(
        self,
        *,
        decks: dict[int, str],
        notetype_id: int = 1,
        field_count: int = 2,
        error: Exception | None = None,
    ) -> None:
        self.decks = decks
        self.notetype_id = notetype_id
        self.field_count = field_count
        self.error = error
        self.fail_add_after: int | None = None
        self._added = 0

    def reset_added(self) -> None:
        """Forget how many cards previous tests added, so ``fail_add_after`` counts from zero."""
        self._added = 0

    @override
    async def add_target(self, deck_id: int) -> AddTarget:
        """Raise the configured error, or resolve ``deck_id`` against the fake's deck list."""
        if self.error is not None:
            raise self.error

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
    async def add_card(self, target: AddTarget, front: str, back: str) -> None:
        """Raise the configured error, or succeed silently — until ``fail_add_after`` runs out."""
        if self.error is not None:
            raise self.error
        if self.fail_add_after is not None and self._added >= self.fail_add_after:
            raise AnkiCardCreationError("The fake gateway was told to fail here")
        self._added += 1
