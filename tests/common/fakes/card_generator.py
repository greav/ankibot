"""In-memory implementation of the CardGenerator port."""

from collections.abc import Mapping
from typing import override

from ankibot.application.add_vocabulary_word import CardFeedback, CardGenerator
from ankibot.domain.card_template import CardTemplate


class FakeCardGenerator(CardGenerator):
    """Fills a card template without calling any LLM, or raises ``error`` instead when one is set.

    ``values``/``error`` stay writable so a test sharing one dispatcher can steer its own run.
    """

    def __init__(self, values: Mapping[str, str] | None = None, error: Exception | None = None) -> None:
        self.values = values if values is not None else {}
        self.error = error

    @override
    async def generate(
        self, word: str, template: CardTemplate, *, feedback: CardFeedback | None = None
    ) -> Mapping[str, str]:
        """Raise the configured error, or return ``values`` when there is none, whatever was asked."""
        if self.error is not None:
            raise self.error
        return dict(self.values)
