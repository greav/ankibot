"""In-memory implementation of the ModelCatalog port."""

from collections.abc import Sequence
from typing import override

from ankibot.application.common.model_catalog import ModelCatalog, ModelOption


class FakeModelCatalog(ModelCatalog):
    """Offers ``options`` with ``default_id`` as the default; both stay writable so a test can steer its run."""

    def __init__(self, options: Sequence[ModelOption], default_id: str) -> None:
        self.options_list = list(options)
        self.default_id = default_id

    @override
    async def options(self) -> Sequence[ModelOption]:
        return list(self.options_list)

    @override
    async def default(self) -> ModelOption:
        return next(option for option in self.options_list if option.id == self.default_id)
