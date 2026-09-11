"""In-memory implementation of the WordSuggester port."""

from collections.abc import Sequence
from typing import override

from ankibot.application.add_vocabulary_word import WordSuggester
from ankibot.application.common.dto.image import Image


class FakeWordSuggester(WordSuggester):
    """Offers ``words`` for any screenshot without calling any LLM, or raises ``error`` when one is set.

    ``words``/``error`` stay writable so a test sharing one dispatcher can steer its own run.
    """

    def __init__(self, words: Sequence[str] | None = None, error: Exception | None = None) -> None:
        self.words = list(words) if words is not None else []
        self.error = error

    @override
    async def suggest(self, image: Image) -> Sequence[str]:
        """Raise the configured error, or return ``words`` when there is none."""
        if self.error is not None:
            raise self.error
        return list(self.words)
