import logging
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
from pydantic import BaseModel, ValidationError

from ankibot.application.add_vocabulary_word import WordSuggester
from ankibot.application.common.dto.image import Image
from ankibot.application.exceptions.generation import CardGenerationError, CardGenerationUnavailableError
from ankibot.infra.llm.failures import failure_reason
from ankibot.infra.llm.images import image_data_url

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class OpenAIWordSuggesterConfig:
    """What the adapter itself decides."""

    model: str
    max_candidates: int


class WordsAnswer(BaseModel):
    """What ``chat.completions.parse`` asks the model for and validates its answer against."""

    words: list[str]


def build_system_prompt(max_candidates: int) -> str:
    """The system-turn prompt asking for at most ``max_candidates`` words worth looking up."""
    return (
        "You read a screenshot of English text a language learner is studying and pick out the "
        f"words or short phrases they would most want to look up. List at most {max_candidates}, "
        "in reading order: rare, advanced or idiomatic ones first, and anything highlighted, "
        "underlined or selected in the screenshot before everything else. Write each in its "
        "dictionary form, spelled as in the text, and nothing else — no definitions."
    )


class OpenAIWordSuggester(WordSuggester):
    """Picks look-up candidates out of a screenshot with OpenAI's structured outputs.

    The screenshot goes to the model directly as an image part — the configured model must accept
    image input; there is no separate OCR step.
    """

    def __init__(self, config: OpenAIWordSuggesterConfig, client: AsyncOpenAI) -> None:
        self._config = config
        self._client = client

    @override
    async def suggest(self, image: Image) -> tuple[str, ...]:
        try:
            return await self._ask(image)
        except CardGenerationError as error:
            logger.warning("Word suggestion by %s failed: %s", self._config.model, failure_reason(error))
            raise

    async def _ask(self, image: Image) -> tuple[str, ...]:
        try:
            response = await self._client.chat.completions.parse(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": build_system_prompt(self._config.max_candidates)},
                    {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_data_url(image)}}]},
                ],
                response_format=WordsAnswer,
            )
        except (APIConnectionError, APITimeoutError, RateLimitError, APIStatusError) as api_error:
            raise CardGenerationUnavailableError from api_error
        except LengthFinishReasonError as length_error:
            raise CardGenerationError("The word suggester's answer was truncated") from length_error
        except ValidationError as validation_error:
            raise CardGenerationError("The word suggester's answer was not a list of words") from validation_error

        message = response.choices[0].message
        if message.refusal is not None:
            raise CardGenerationError(f"The word suggester refused to answer: {message.refusal}")
        if message.parsed is None:
            raise CardGenerationError("The word suggester returned no content")

        # The schema cannot carry the cap (strict mode does not reliably honor maxItems), so it is
        # enforced here.
        return tuple(message.parsed.words[: self._config.max_candidates])
