from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from ankibot.application.english_card_generation.models import CardTemplate, GeneratedCard
from ankibot.application.english_card_generation.protocols import CardGenerator
from ankibot.application.exceptions.card_generation import LLMError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenAICardGeneratorConfig:
    api_key: str
    model: str
    temperature: float = 0.2
    max_output_tokens: int = 600


class OpenAICardGenerator(CardGenerator):
    def __init__(
        self,
        config: OpenAICardGeneratorConfig,
        client: Optional[AsyncOpenAI] = None,
    ) -> None:
        self._config = config
        self._client = client or AsyncOpenAI(api_key=config.api_key)

    async def generate_card(self, word: str, template: CardTemplate) -> GeneratedCard:
        prompt = self._build_prompt(word, template)
        logger.info("Requesting card generation for %s", word)

        try:
            response = await self._client.responses.create(
                model=self._config.model,
                input=prompt,
                temperature=self._config.temperature,
                max_output_tokens=self._config.max_output_tokens,
                response_format=self._response_schema(),
            )
        except Exception as exc:  # pragma: no cover - network failure path
            raise LLMError(str(exc)) from exc

        content = self._extract_text(response)
        return self._parse_payload(content, word)

    def _build_prompt(self, word: str, template: CardTemplate) -> str:
        instructions = template.prompt.strip()
        fields_description = ", ".join(template.field_mapping.keys())
        return f"{instructions}\n\nWord: {word}\nRespond with a JSON object containing the keys {fields_description}."

    def _response_schema(self) -> Dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "english_vocabulary_card",
                "schema": {
                    "type": "object",
                    "properties": {
                        "word": {"type": "string"},
                        "definition": {"type": "string"},
                        "part_of_speech": {"type": "string"},
                        "synonyms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "russian_translations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "example_sentences": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                    },
                    "required": [
                        "word",
                        "definition",
                        "part_of_speech",
                        "synonyms",
                        "russian_translations",
                        "example_sentences",
                    ],
                    "additionalProperties": False,
                },
            },
        }

    def _extract_text(self, response: Any) -> str:
        try:
            return response.output[0].content[0].text  # type: ignore[index]
        except (AttributeError, IndexError, KeyError):
            pass

        try:
            return response.choices[0].message.content  # type: ignore[index]
        except (AttributeError, IndexError, KeyError) as exc:  # pragma: no cover - defensive
            raise LLMError("Unable to parse OpenAI response payload") from exc

    def _parse_payload(self, raw_json: str, fallback_word: str) -> GeneratedCard:
        try:
            payload: Dict[str, Any] = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise LLMError("OpenAI returned malformed JSON") from exc

        return GeneratedCard(
            word=payload.get("word", fallback_word),
            definition=payload.get("definition", ""),
            part_of_speech=payload.get("part_of_speech", ""),
            synonyms=self._ensure_list(payload.get("synonyms")),
            russian_translations=self._ensure_list(payload.get("russian_translations")),
            example_sentences=self._ensure_list(payload.get("example_sentences")),
        )

    def _ensure_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        if value is None:
            return []
        return [str(value)]
