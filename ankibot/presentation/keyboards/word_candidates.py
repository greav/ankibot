"""The word picker shown under a screenshot the learner sent without naming a word.

Router-free like ``keyboards/decks.py``. Only an index travels in ``callback_data``; the candidate
words live in FSM data, which keeps a long phrase clear of Telegram's 64-byte limit.
"""

from collections.abc import Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CANDIDATES_PER_ROW = 2


class WordCandidateCallback(CallbackData, prefix="wordpick"):
    """Picks the candidate at ``index`` in the stored list."""

    index: int


def word_candidates_keyboard(words: Sequence[str]) -> InlineKeyboardMarkup:
    """One button per candidate, labelled with the word itself, two to a row."""
    buttons = [
        InlineKeyboardButton(text=word, callback_data=WordCandidateCallback(index=index).pack())
        for index, word in enumerate(words)
    ]
    rows = [buttons[start : start + CANDIDATES_PER_ROW] for start in range(0, len(buttons), CANDIDATES_PER_ROW)]
    return InlineKeyboardMarkup(inline_keyboard=rows)
