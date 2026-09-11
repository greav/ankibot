"""In-memory implementation of the SnippetCardsGenerator port."""

from collections.abc import Sequence
from typing import override

from ankibot.application.add_snippet_cards import DraftCard, Snippet, SnippetCardsGenerator


class FakeSnippetCardsGenerator(SnippetCardsGenerator):
    """Distills a snippet without calling any LLM, or raises ``error`` instead when one is set.

    ``cards``/``error`` stay writable so a test sharing one dispatcher can steer its own run.
    """

    def __init__(self, cards: Sequence[DraftCard] | None = None, error: Exception | None = None) -> None:
        self.cards = list(cards) if cards is not None else []
        self.error = error

    @override
    async def generate(
        self, snippet: Snippet, *, kept: Sequence[DraftCard] = (), feedback: str | None = None
    ) -> Sequence[DraftCard]:
        """Raise the configured error, or return ``cards`` when there is none, whatever was kept or asked."""
        if self.error is not None:
            raise self.error
        return list(self.cards)
