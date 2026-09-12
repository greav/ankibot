from dataclasses import dataclass

from ankibot.application.common.model_catalog import ModelCatalog, ModelOption
from ankibot.application.common.selected_model_store import SelectedModelStore, chosen_model


@dataclass(frozen=True, kw_only=True)
class ListModelsRequest:
    user_id: int


@dataclass(frozen=True, kw_only=True)
class ListModelsResult:
    """The models on offer, and the one the user's next card would be written by.

    ``selected_id`` is what ``chosen_model`` resolves to, so the mark sits on the default when the
    user has never picked, and moves off a retired choice the way the next card would.
    """

    options: tuple[ModelOption, ...]
    selected_id: str


class ListModels:
    def __init__(self, catalog: ModelCatalog, selected_models: SelectedModelStore) -> None:
        self._catalog = catalog
        self._selected_models = selected_models

    async def execute(self, request: ListModelsRequest) -> ListModelsResult:
        options = tuple(await self._catalog.options())
        selected_id = (await chosen_model(self._selected_models, self._catalog, request.user_id)).id
        return ListModelsResult(options=options, selected_id=selected_id)
