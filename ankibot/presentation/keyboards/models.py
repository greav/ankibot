"""The /model picker keyboard.

Router-free like ``keyboards/decks.py``, so a future flow can open the same picker without
attaching the ``/model`` router twice.
"""

from collections.abc import Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ankibot.application.common.model_catalog import ModelOption


class ModelCallback(CallbackData, prefix="model"):
    """Picks a model. Only the catalog id travels, so the label cannot overflow the 64-byte limit."""

    id: str


def model_keyboard(options: Sequence[ModelOption], selected_id: str) -> InlineKeyboardMarkup:
    """One button per model, one per row, the selected one marked. No paging: the catalog is short."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"✓ {option.label}" if option.id == selected_id else option.label,
                callback_data=ModelCallback(id=option.id).pack(),
            )
        ]
        for option in options
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
