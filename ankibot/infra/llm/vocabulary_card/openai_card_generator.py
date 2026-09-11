import logging
from dataclasses import dataclass
from typing import override

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

from ankibot.application.add_vocabulary_word.generate_card import CardFeedback, CardGenerator
from ankibot.application.common.dto.image import Image
from ankibot.application.exceptions.generation import CardGenerationError, CardGenerationUnavailableError
from ankibot.domain.card_template import CardTemplate
from ankibot.infra.llm.failures import failure_reason
from ankibot.infra.llm.vocabulary_card.parsing import parse_fields
from ankibot.infra.llm.vocabulary_card.prompt import SYSTEM_PROMPT, build_user_content, response_schema

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class OpenAICardGeneratorConfig:
    """What the adapter itself decides."""

    model: str


class OpenAICardGenerator(CardGenerator):
    """Fills a card template's fields with OpenAI's structured outputs (strict JSON schema).

    A screenshot context goes to the model directly as an image part — the configured model must
    accept image input; there is no separate OCR step.
    """

    def __init__(self, config: OpenAICardGeneratorConfig, client: AsyncOpenAI) -> None:
        self._config = config
        self._client = client

    @override
    async def generate(
        self,
        word: str,
        template: CardTemplate,
        *,
        context: Image | None = None,
        feedback: CardFeedback | None = None,
    ) -> dict[str, str]:
        try:
            return await self._ask(word, template, context, feedback)
        except CardGenerationError as error:
            logger.warning("Vocabulary card generation by %s failed: %s", self._config.model, failure_reason(error))
            raise

    async def _ask(
        self, word: str, template: CardTemplate, context: Image | None, feedback: CardFeedback | None
    ) -> dict[str, str]:
        try:
            response = await self._client.chat.completions.create(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_content(word, template, context, feedback)},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "vocabulary_card",
                        "strict": True,
                        "schema": response_schema(template),
                    },
                },
            )
        except (APIConnectionError, APITimeoutError, RateLimitError, APIStatusError) as api_error:
            raise CardGenerationUnavailableError from api_error

        choice = response.choices[0]
        if choice.message.refusal is not None:
            raise CardGenerationError(f"The card generator refused to answer: {choice.message.refusal}")
        if choice.finish_reason == "length":
            raise CardGenerationError("The card generator's answer was truncated")
        if choice.message.content is None:
            raise CardGenerationError("The card generator returned no content")

        return parse_fields(choice.message.content)
