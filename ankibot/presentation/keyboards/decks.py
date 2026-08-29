"""The deck picker keyboard, shared by /decks and /addcard.

Router-free on purpose: both handler modules build the same keyboard, and a module owning a
``Router`` cannot be imported by another without attaching it twice.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ankibot.application.manage_decks import Deck

DECK_PAGE_SIZE = 8


class DeckCallback(CallbackData, prefix="deck"):
    """Picks a deck. Only the id travels, so a long deck name cannot overflow the 64-byte limit."""

    id: int


class DeckPageCallback(CallbackData, prefix="deckpage"):
    page: int


@dataclass(frozen=True, kw_only=True)
class DeckPage:
    decks: list[Deck]
    page: int
    has_prev: bool
    has_next: bool


def page_of(decks: Sequence[Deck], page: int) -> DeckPage:
    """Slice ``decks`` into one keyboard page, clamping ``page`` into range."""
    last_page = max(0, (len(decks) - 1) // DECK_PAGE_SIZE)
    clamped = min(max(page, 0), last_page)
    start = clamped * DECK_PAGE_SIZE

    return DeckPage(
        decks=list(decks[start : start + DECK_PAGE_SIZE]),
        page=clamped,
        has_prev=clamped > 0,
        has_next=clamped < last_page,
    )


def deck_keyboard(page: DeckPage, selected_deck_id: int | None) -> InlineKeyboardMarkup:
    """One button per deck on the page, the selected one marked, plus paging arrows when needed."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"✓ {deck.name}" if deck.id == selected_deck_id else deck.name,
                callback_data=DeckCallback(id=deck.id).pack(),
            )
        ]
        for deck in page.decks
    ]

    arrows = []
    if page.has_prev:
        arrows.append(InlineKeyboardButton(text="◀", callback_data=DeckPageCallback(page=page.page - 1).pack()))
    if page.has_next:
        arrows.append(InlineKeyboardButton(text="▶", callback_data=DeckPageCallback(page=page.page + 1).pack()))
    if arrows:
        rows.append(arrows)

    return InlineKeyboardMarkup(inline_keyboard=rows)
