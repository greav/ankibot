"""In-memory implementation of the SelectedModelStore port."""

from typing import override

from ankibot.application.common.selected_model_store import SelectedModelStore


class FakeSelectedModelStore(SelectedModelStore):
    """Remembers model choices in a public dict the reset fixture can clear."""

    def __init__(self) -> None:
        self.models: dict[int, str] = {}

    @override
    async def get_model(self, user_id: int) -> str | None:
        return self.models.get(user_id)

    @override
    async def set_model(self, user_id: int, model_id: str) -> None:
        self.models[user_id] = model_id
