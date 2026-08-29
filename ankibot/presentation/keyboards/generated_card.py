"""The generated-card confirmation keyboard, router-free like ``keyboards/decks.py``.

No payload travels in ``callback_data``: the word and the generated field values live in FSM data,
which is what keeps this clear of Telegram's 64-byte limit regardless of how many fields a notetype
carries.
"""

from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class GeneratedCardCallback(CallbackData, prefix="gencard"):
    """Acts on the pending preview: save it, generate a fresh one, or drop it."""

    action: Literal["save", "regenerate", "cancel"]


def generated_card_keyboard() -> InlineKeyboardMarkup:
    """The Save / Regenerate / Cancel row shown under a generated card preview."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Save", callback_data=GeneratedCardCallback(action="save").pack()),
                InlineKeyboardButton(
                    text="Regenerate", callback_data=GeneratedCardCallback(action="regenerate").pack()
                ),
                InlineKeyboardButton(text="Cancel", callback_data=GeneratedCardCallback(action="cancel").pack()),
            ]
        ]
    )
