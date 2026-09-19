from dataclasses import dataclass
from typing import Literal, cast

from openai import AsyncOpenAI, Omit, omit
from openai.types.shared import ReasoningEffort

from ankibot.application.common.model_catalog import ModelOption

type OpenAIReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
"""The values OpenAI accepts for ``reasoning_effort``; what the catalog config validates against."""


@dataclass(frozen=True, kw_only=True)
class OpenAIClientConfig:
    """What the SDK client needs. Never reaches an adapter's own config."""

    api_key: str
    base_url: str
    timeout_seconds: float
    max_retries: int


def build_openai_client(config: OpenAIClientConfig) -> AsyncOpenAI:
    """Construct the SDK client. Tests substitute the transport instead of calling this."""
    return AsyncOpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.timeout_seconds,
        max_retries=config.max_retries,
    )


def reasoning_effort_argument(
    model: ModelOption, override: OpenAIReasoningEffort | None = None
) -> ReasoningEffort | Omit:
    """The ``reasoning_effort`` to send for ``model``: its catalog value, or nothing at all.

    Omitting the parameter, rather than sending null, is what keeps a model that takes none
    (gpt-4.1) from rejecting the request — so ``override``, a task's own effort, applies only to
    a model the catalog gave an effort to, and is dropped for one that takes no such setting.
    The cast is safe because ``ModelEntryConfig`` validated the catalog value against
    ``OpenAIReasoningEffort`` when the config loaded.
    """
    if model.reasoning_effort is None:
        return omit
    return cast(ReasoningEffort, override or model.reasoning_effort)
