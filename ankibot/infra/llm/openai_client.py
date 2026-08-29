from dataclasses import dataclass

from openai import AsyncOpenAI


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
