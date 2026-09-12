import logging
from dataclasses import dataclass

from ankibot.application.common.model_catalog import ModelCatalog
from ankibot.application.common.selected_model_store import SelectedModelStore
from ankibot.application.exceptions.models import ModelNotOfferedError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SelectModelRequest:
    user_id: int
    model_id: str


@dataclass(frozen=True, kw_only=True)
class SelectModelResult:
    label: str


class SelectModel:
    def __init__(self, catalog: ModelCatalog, selected_models: SelectedModelStore) -> None:
        self._catalog = catalog
        self._selected_models = selected_models

    async def execute(self, request: SelectModelRequest) -> SelectModelResult:
        # The id is checked against the catalog rather than trusted from the keyboard: a button
        # rendered before a config change, or a forged callback, must not store a model the
        # generators cannot call.
        options = await self._catalog.options()
        label = next((option.label for option in options if option.id == request.model_id), None)
        if label is None:
            logger.info("The picked model %s is not in the catalog", request.model_id)
            raise ModelNotOfferedError

        await self._selected_models.set_model(request.user_id, request.model_id)
        return SelectModelResult(label=label)
