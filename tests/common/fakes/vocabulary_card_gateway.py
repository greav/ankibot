"""In-memory implementation of the VocabularyCardGateway port."""

from collections.abc import Sequence
from typing import override

from ankibot.application.add_vocabulary_word import VocabularyCardGateway, VocabularyTarget
from ankibot.domain.card_template import CardTemplate

DEFAULT_TEMPLATE = CardTemplate(name="English Words V2", fields=("Word", "Meaning", "Example"))


class FakeVocabularyCardGateway(VocabularyCardGateway):
    """Targets and adds vocabulary notes without leaving the process, or raises ``error`` when set.

    Every field stays writable so a test sharing one dispatcher can steer the run it is about to make.
    """

    def __init__(
        self,
        *,
        deck_id: int = 1,
        deck_name: str = "English Words V2",
        notetype_id: int = 1,
        template: CardTemplate = DEFAULT_TEMPLATE,
        error: Exception | None = None,
    ) -> None:
        self.deck_id = deck_id
        self.deck_name = deck_name
        self.notetype_id = notetype_id
        self.template = template
        self.error = error

    @override
    async def target(self) -> VocabularyTarget:
        """Raise the configured error, or resolve the fake's current deck/notetype/template."""
        if self.error is not None:
            raise self.error
        return VocabularyTarget(
            deck_id=self.deck_id,
            deck_name=self.deck_name,
            notetype_id=self.notetype_id,
            template=self.template,
        )

    @override
    async def add_note(self, target: VocabularyTarget, fields: Sequence[str]) -> None:
        """Raise the configured error, or succeed silently when there is none."""
        if self.error is not None:
            raise self.error
