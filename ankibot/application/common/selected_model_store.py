import logging
from abc import abstractmethod
from collections.abc import Sequence
from typing import Protocol

from ankibot.application.common.model_catalog import ModelCatalog, ModelOption

logger = logging.getLogger(__name__)


class SelectedModelStore(Protocol):
    """Remembers which model a Telegram user wants their cards written by."""

    @abstractmethod
    async def get_model(self, user_id: int) -> str | None:
        """Return the model id the user picked, or None when they have not picked one."""
        raise NotImplementedError

    @abstractmethod
    async def set_model(self, user_id: int, model_id: str) -> None:
        """Remember ``model_id`` as the user's model."""
        raise NotImplementedError


def resolve_model(stored: str | None, offered: Sequence[ModelOption], default: ModelOption) -> ModelOption:
    """The model to call: the stored one while the catalog still offers it, otherwise the default.

    A stored id drops out of the catalog when the operator retires a model; falling back keeps
    the user's next card working instead of failing on a model the key can no longer call.
    """
    return next((option for option in offered if option.id == stored), default)


async def chosen_model(store: SelectedModelStore, catalog: ModelCatalog, user_id: int) -> ModelOption:
    """The model ``user_id`` gets their cards written by.

    Unlike ``chosen_deck``, no choice is not an error: the catalog's default serves everyone who
    has not opened /model, so the bot works out of the box.
    """
    stored = await store.get_model(user_id)
    model = resolve_model(stored, await catalog.options(), await catalog.default())
    if stored is not None and model.id != stored:
        logger.info("User %s's model %s is no longer offered; using %s", user_id, stored, model.id)
    return model
