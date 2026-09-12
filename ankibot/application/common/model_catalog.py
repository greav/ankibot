from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, kw_only=True)
class ModelOption:
    """One model /model offers: the id the generators are called with, and the name the user sees.

    ``reasoning_effort`` is how hard the model thinks before answering, in the provider's own
    vocabulary; None leaves the provider's default in place, and is the only choice for a model
    that takes no such setting. A card is a few hundred tokens: a model that reasons by default
    answers it slower and dearer for no better card, so the catalog names the effort per model.
    """

    id: str
    label: str
    reasoning_effort: str | None = None


class ModelCatalog(Protocol):
    """The models a user may pick from, in the order they are offered."""

    @abstractmethod
    async def options(self) -> Sequence[ModelOption]:
        """Return every model on offer, in presentation order."""
        raise NotImplementedError

    @abstractmethod
    async def default(self) -> ModelOption:
        """Return the model a user who has not picked one gets."""
        raise NotImplementedError
