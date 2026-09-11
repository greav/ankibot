import logging
from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ankibot.application.common.dto.image import Image
from ankibot.application.exceptions.generation import CardGenerationEmptyError

logger = logging.getLogger(__name__)


class WordSuggester(Protocol):
    """Picks out of a screenshot of English text the words a learner would want to look up."""

    @abstractmethod
    async def suggest(self, image: Image) -> Sequence[str]:
        """Return candidate words in reading order, possibly none; how many at most is the adapter's call.

        Raises ``CardGenerationUnavailableError`` when the backend cannot be reached, and
        ``CardGenerationError`` when its answer cannot be read.
        """
        raise NotImplementedError


def clean_candidates(words: Sequence[str]) -> tuple[str, ...]:
    """Strip the candidates, drop blanks, and keep the first of any case-insensitive repeats."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for word in words:
        stripped = word.strip()
        key = stripped.casefold()
        if not stripped or key in seen:
            continue
        seen.add(key)
        cleaned.append(stripped)
    return tuple(cleaned)


@dataclass(frozen=True, kw_only=True)
class SuggestWordsRequest:
    image: Image


@dataclass(frozen=True, kw_only=True)
class SuggestedWords:
    """The words offered for the learner to pick one from."""

    words: tuple[str, ...]


class SuggestWords:
    def __init__(self, suggester: WordSuggester) -> None:
        self._suggester = suggester

    async def execute(self, request: SuggestWordsRequest) -> SuggestedWords:
        words = clean_candidates(await self._suggester.suggest(request.image))
        if not words:
            logger.info("The screenshot held no word worth looking up")
            raise CardGenerationEmptyError
        return SuggestedWords(words=words)
