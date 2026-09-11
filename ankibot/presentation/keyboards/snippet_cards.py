"""The snippet-cards confirmation keyboard: a toggle per generated card, then the action row.

Separate from ``keyboards/generated_card.py``, which /word uses for a single card and needs no
selection. Router-free like ``keyboards/decks.py``.

Only a card's index travels in ``callback_data``; the cards themselves and the selection live in
FSM data, which keeps every button clear of Telegram's 64-byte limit.
"""

from collections.abc import Sequence
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Telegram allows up to 8 buttons in a row, but at max_cards: 8 two rows of four read better.
TOGGLES_PER_ROW = 4

SELECTED_MARK = "☑"
UNSELECTED_MARK = "☐"


class SnippetCardCallback(CallbackData, prefix="snipcard"):
    """Toggles one card of the pending preview, or acts on the whole selection.

    ``index`` matters only for ``toggle``; ``-1`` keeps the payload short for the other actions.
    """

    action: Literal["toggle", "save", "regenerate", "cancel"]
    index: int = -1


def toggled(selection: Sequence[bool], index: int) -> tuple[bool, ...]:
    """Return ``selection`` with the card at ``index`` flipped; an index out of range changes nothing."""
    if not 0 <= index < len(selection):
        return tuple(selection)
    return tuple(not chosen if position == index else chosen for position, chosen in enumerate(selection))


def regenerate_label(selection: Sequence[bool]) -> str:
    """``Regenerate`` for the whole batch, or ``Regenerate N`` for the N unticked cards it will replace."""
    unticked = len(selection) - sum(selection)
    return "Regenerate" if unticked == 0 else f"Regenerate {unticked}"


def snippet_cards_keyboard(selection: Sequence[bool]) -> InlineKeyboardMarkup:
    """Numbered toggles matching the preview's numbering, then Save / Regenerate (each with a count) / Cancel."""
    toggles = [
        InlineKeyboardButton(
            text=f"{SELECTED_MARK if chosen else UNSELECTED_MARK} {index + 1}",
            callback_data=SnippetCardCallback(action="toggle", index=index).pack(),
        )
        for index, chosen in enumerate(selection)
    ]
    rows = [toggles[start : start + TOGGLES_PER_ROW] for start in range(0, len(toggles), TOGGLES_PER_ROW)]

    chosen_count = sum(selection)
    rows.append(
        [
            InlineKeyboardButton(
                text=f"Save {chosen_count} of {len(selection)}",
                callback_data=SnippetCardCallback(action="save").pack(),
            ),
            InlineKeyboardButton(
                text=regenerate_label(selection), callback_data=SnippetCardCallback(action="regenerate").pack()
            ),
            InlineKeyboardButton(text="Cancel", callback_data=SnippetCardCallback(action="cancel").pack()),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
