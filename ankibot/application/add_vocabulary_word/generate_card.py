from abc import abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from ankibot.application.add_vocabulary_word.ports import VocabularyCardGateway
from ankibot.application.exceptions.generation import CardGenerationIncompleteError
from ankibot.domain.card_template import CardTemplate, in_template_order, missing_fields


class CardGenerator(Protocol):
    """Fills a card template's fields for one word."""

    @abstractmethod
    async def generate(self, word: str, template: CardTemplate) -> Mapping[str, str]:
        """Return a value per template field, keyed by field name.

        Raises ``CardGenerationUnavailableError`` when the backend cannot be reached, and
        ``CardGenerationError`` when its answer cannot be read.
        """
        raise NotImplementedError


@dataclass(frozen=True, kw_only=True)
class GenerateCardRequest:
    word: str


@dataclass(frozen=True, kw_only=True)
class GeneratedCard:
    """The filled card the user is asked to confirm, fields in the notetype's own order."""

    deck_name: str
    fields: tuple[tuple[str, str], ...]


class GenerateCard:
    def __init__(self, gateway: VocabularyCardGateway, generator: CardGenerator) -> None:
        self._gateway = gateway
        self._generator = generator

    async def execute(self, request: GenerateCardRequest) -> GeneratedCard:
        target = await self._gateway.target()
        values = await self._generator.generate(request.word, target.template)
        if missing := missing_fields(target.template, values):
            raise CardGenerationIncompleteError(f"The generator left {', '.join(missing)} empty")
        return GeneratedCard(
            deck_name=target.deck_name,
            fields=tuple(zip(target.template.fields, in_template_order(target.template, values), strict=True)),
        )
