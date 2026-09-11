"""The generated-card confirmation keyboard for the word dialog, router-free like ``keyboards/decks.py``.

No payload travels in ``callback_data``: the word and the generated field values live in FSM data,
which is what keeps this clear of Telegram's 64-byte limit regardless of how many fields a notetype
carries.
"""

from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class GeneratedCardCallback(CallbackData, prefix="gencard"):
    """Acts on the pending preview: save it, generate a fresh one — after a note, or not — or drop it."""

    action: Literal["save", "regenerate", "feedback", "cancel"]


def generated_card_keyboard() -> InlineKeyboardMarkup:
    """Save / Cancel, then the two Regenerates, shown under a generated card preview."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Save", callback_data=GeneratedCardCallback(action="save").pack()),
                InlineKeyboardButton(text="Cancel", callback_data=GeneratedCardCallback(action="cancel").pack()),
            ],
            [
                InlineKeyboardButton(
                    text="Regenerate", callback_data=GeneratedCardCallback(action="regenerate").pack()
                ),
                InlineKeyboardButton(
                    text="Regenerate with feedback", callback_data=GeneratedCardCallback(action="feedback").pack()
                ),
            ],
        ]
    )
