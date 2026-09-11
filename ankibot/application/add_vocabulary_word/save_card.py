import logging
from collections.abc import Mapping
from dataclasses import dataclass

from ankibot.application.add_vocabulary_word.ports import VocabularyCardGateway
from ankibot.application.exceptions.generation import CardGenerationIncompleteError
from ankibot.domain.card_template import in_template_order, missing_fields

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SaveCardRequest:
    values: Mapping[str, str]


@dataclass(frozen=True, kw_only=True)
class SaveCardResult:
    deck_name: str


class SaveCard:
    def __init__(self, gateway: VocabularyCardGateway) -> None:
        self._gateway = gateway

    async def execute(self, request: SaveCardRequest) -> SaveCardResult:
        target = await self._gateway.target()
        if missing := missing_fields(target.template, request.values):
            logger.warning("Vocabulary card no longer fits the notetype: %s empty", ", ".join(missing))
            raise CardGenerationIncompleteError(f"The generator left {', '.join(missing)} empty")
        await self._gateway.add_note(target, in_template_order(target.template, request.values))
        return SaveCardResult(deck_name=target.deck_name)
