"""The model catalog, as the operator writes it in ``configs/config.yaml``.

A static list rather than the provider's ``/v1/models``: that endpoint lists everything the key may
call, and says nothing about structured outputs or image input, which every entry here must support.
"""

from dataclasses import dataclass
from typing import Literal, override

from ankibot.application.common.model_catalog import ModelCatalog, ModelOption
from ankibot.infra.llm.openai_client import OpenAIReasoningEffort


@dataclass(frozen=True, kw_only=True)
class ModelEntryConfig:
    id: str
    """The id the provider's API is called with."""
    provider: Literal["openai"]
    """Which adapter family serves it; only one exists today, so nothing routes on it yet."""
    label: str
    """What the user sees on the /model keyboard."""
    reasoning_effort: OpenAIReasoningEffort | None = None
    """How hard the model thinks per call. Omit it for a model that takes no such setting; set it
    to ``none`` for a model that reasons by default, or every card pays for thinking tokens."""


@dataclass(frozen=True, kw_only=True)
class ModelCatalogConfig:
    default: str
    """The id served to a user who has not picked; must be one of ``models``."""
    models: tuple[ModelEntryConfig, ...]


class ConfigModelCatalog(ModelCatalog):
    """Offers the configured models in the configured order.

    A duplicate id or a default outside the list raises ``ValueError`` at construction:
    ``warm_up`` resolves this port before polling starts, so a bad catalog refuses to start the bot
    instead of offering a keyboard that cannot be honored.
    """

    def __init__(self, config: ModelCatalogConfig) -> None:
        ids = [entry.id for entry in config.models]
        if len(set(ids)) != len(ids):
            msg = f"Model catalog lists an id more than once: {ids}"
            raise ValueError(msg)
        if config.default not in ids:
            msg = f"Model catalog default {config.default!r} is not one of its models: {ids}"
            raise ValueError(msg)
        self._options = tuple(
            ModelOption(id=entry.id, label=entry.label, reasoning_effort=entry.reasoning_effort)
            for entry in config.models
        )
        self._default = next(option for option in self._options if option.id == config.default)

    @override
    async def options(self) -> tuple[ModelOption, ...]:
        return self._options

    @override
    async def default(self) -> ModelOption:
        return self._default
