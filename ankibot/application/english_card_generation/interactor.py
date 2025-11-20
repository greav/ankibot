from __future__ import annotations

import logging
from typing import Any

from ankibot.application.exceptions.card_generation import (
    AnkiAPIError,
    CardGenerationError,
    LLMError,
)

from .dtos import CardGenerationInputDTO, CardGenerationOutputDTO
from .models import AddNotePayload, CardTemplate, GeneratedCard
from .protocols import AnkiWebGateway, CardGenerator

logger = logging.getLogger(__name__)


class GenerateEnglishCardInteractor:
    def __init__(
        self,
        card_generator: CardGenerator,
        anki_gateway: AnkiWebGateway,
        template: CardTemplate,
    ) -> None:
        self._card_generator = card_generator
        self._anki_gateway = anki_gateway
        self._template = template

    async def __call__(self, dto: CardGenerationInputDTO) -> CardGenerationOutputDTO:
        logger.info("Generating card for word %s", dto.word)

        card = await self._generate_card(dto)
        payload = await self._prepare_payload(card)

        try:
            note_id = await self._anki_gateway.add_note(payload)
        except CardGenerationError:
            raise
        except Exception as exc:  # pragma: no cover - defensive safety net
            raise AnkiAPIError(str(exc)) from exc

        logger.info("Successfully generated card for %s (note_id=%s)", dto.word, note_id)
        return CardGenerationOutputDTO(success=True, note_id=note_id)

    async def _generate_card(self, dto: CardGenerationInputDTO) -> GeneratedCard:
        try:
            return await self._card_generator.generate_card(dto.word, self._template)
        except CardGenerationError:
            raise
        except Exception as exc:  # pragma: no cover - defensive safety net
            raise LLMError(str(exc)) from exc

    async def _prepare_payload(self, card: GeneratedCard) -> AddNotePayload:
        try:
            deck_id = await self._anki_gateway.get_default_deck_id()
            editor_info = await self._anki_gateway.get_editor_info()
        except CardGenerationError:
            raise
        except Exception as exc:  # pragma: no cover - defensive safety net
            raise AnkiAPIError(str(exc)) from exc

        fields = [self._resolve_field_value(field_name, card) for field_name in editor_info.field_order]

        return AddNotePayload(
            deck_id=deck_id,
            notetype_id=editor_info.notetype_id,
            fields=fields,
            tags=self._template.tags,
        )

    def _resolve_field_value(self, field_name: str, card: GeneratedCard) -> str:
        attr_name = self._template.field_mapping.get(field_name)
        if not attr_name:
            return ""

        value: Any = getattr(card, attr_name, "")
        if isinstance(value, list):
            return self._template.list_delimiter.join(value)

        return str(value) if value is not None else ""
