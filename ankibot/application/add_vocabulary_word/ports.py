from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ankibot.domain.card_template import CardTemplate


@dataclass(frozen=True, kw_only=True)
class VocabularyTarget:
    """Where vocabulary cards go, and the shape one has to have."""

    deck_id: int
    deck_name: str
    notetype_id: int
    template: CardTemplate


class VocabularyCardGateway(Protocol):
    """Reads the vocabulary card template and writes filled cards to the flashcard backend."""

    @abstractmethod
    async def target(self) -> VocabularyTarget:
        """Resolve the configured deck and notetype.

        Raises ``AnkiTemplateTargetNotFoundError`` / ``AnkiSessionExpiredError`` / ``AnkiCardCreationError``.
        """
        raise NotImplementedError

    @abstractmethod
    async def add_note(self, target: VocabularyTarget, fields: Sequence[str]) -> None:
        """Add a note whose plain-text values are ordered as ``target.template`` lists its fields."""
        raise NotImplementedError
