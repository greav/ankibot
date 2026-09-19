import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import override

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    LengthFinishReasonError,
    RateLimitError,
)
from pydantic import ValidationError

from ankibot.application.add_snippet_cards import DraftCard, Snippet, SnippetCardsGenerator
from ankibot.application.common.model_catalog import ModelOption
from ankibot.application.exceptions.generation import CardGenerationError, CardGenerationUnavailableError
from ankibot.infra.llm.failures import failure_reason
from ankibot.infra.llm.openai_client import OpenAIReasoningEffort, reasoning_effort_argument
from ankibot.infra.llm.snippet_cards.parsing import CardsAnswer, to_draft_cards
from ankibot.infra.llm.snippet_cards.prompt import build_system_prompt, build_user_content

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class OpenAISnippetCardsGeneratorConfig:
    """What the adapter itself decides."""

    max_cards: int
    reasoning_effort: OpenAIReasoningEffort | None
    """How hard the model thinks over a passage, overriding the catalog's per-model value.

    Picking which claims deserve a card is a judgment call, unlike filling a word's fields, so
    this task is worth more thinking than the catalog pins for cheap calls. None keeps the
    catalog's value; a model the catalog gave no effort to ignores this either way."""


class OpenAISnippetCardsGenerator(SnippetCardsGenerator):
    """Distills a passage into front/back cards with OpenAI's structured outputs.

    ``chat.completions.parse`` sends the strict JSON schema the SDK derives from ``CardsAnswer``
    and validates the answer against the same model, so the shape is declared exactly once. A
    screenshot goes to the model directly as an image part — every model the catalog offers must
    accept image input; there is no separate OCR step.
    """

    def __init__(self, config: OpenAISnippetCardsGeneratorConfig, client: AsyncOpenAI) -> None:
        self._config = config
        self._client = client

    @override
    async def generate(
        self, snippet: Snippet, *, model: ModelOption, kept: Sequence[DraftCard] = (), feedback: str | None = None
    ) -> tuple[DraftCard, ...]:
        try:
            return await self._ask(model, snippet, kept, feedback)
        except CardGenerationError as error:
            logger.warning("Snippet card generation by %s failed: %s", model.id, failure_reason(error))
            raise

    async def _ask(
        self, model: ModelOption, snippet: Snippet, kept: Sequence[DraftCard], feedback: str | None
    ) -> tuple[DraftCard, ...]:
        # The kept cards count against the cap, so the batch as a whole stays within it; the model
        # is always allowed at least one, or the call would be pointless.
        remaining = max(self._config.max_cards - len(kept), 1)
        try:
            response = await self._client.chat.completions.parse(
                model=model.id,
                reasoning_effort=reasoning_effort_argument(model, self._config.reasoning_effort),
                messages=[
                    {"role": "system", "content": build_system_prompt(remaining)},
                    {"role": "user", "content": build_user_content(snippet, kept, feedback)},
                ],
                response_format=CardsAnswer,
            )
        except (APIConnectionError, APITimeoutError, RateLimitError, APIStatusError) as api_error:
            raise CardGenerationUnavailableError from api_error
        except LengthFinishReasonError as length_error:
            raise CardGenerationError("The card generator's answer was truncated") from length_error
        except ValidationError as validation_error:
            raise CardGenerationError(
                "The card generator's answer was not a list of front/back cards"
            ) from validation_error

        message = response.choices[0].message
        if message.refusal is not None:
            raise CardGenerationError(f"The card generator refused to answer: {message.refusal}")
        if message.parsed is None:
            raise CardGenerationError("The card generator returned no content")

        return to_draft_cards(message.parsed, max_cards=remaining)
