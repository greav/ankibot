"""The deck picker keyboard, shared by /decks, /addcard and the snippet preview.

Router-free on purpose: several handler modules build the same keyboard, and a module owning a
``Router`` cannot be imported by another without attaching it twice.

The picker has three modes. ``PICK`` is the plain list a flow that merely needs a target opens
(``/addcard``, a snippet preview). ``MANAGE`` is what ``/decks`` opens: the same list plus a row
to create a deck and a row into ``DELETE`` mode, where tapping a deck asks to delete it. Deleting
sits behind that extra tap on purpose, so a learner mid-card is never one tap from losing a deck,
and so the list keeps full-width rows: Telegram splits a row evenly between its buttons.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ankibot.application.manage_decks import Deck

DECK_PAGE_SIZE = 8
NEW_DECK_LABEL = "➕ New deck"
DELETE_MODE_LABEL = "➖ Delete deck"
BACK_LABEL = "◁ Back"
CONFIRM_DELETE_LABEL = "Delete"
CANCEL_LABEL = "Cancel"


class PickerMode(StrEnum):
    PICK = "pick"
    MANAGE = "manage"
    DELETE = "delete"


class DeckCallback(CallbackData, prefix="deck"):
    """Picks a deck. Only the id travels, so a long deck name cannot overflow the 64-byte limit."""

    id: int


class DeckPageCallback(CallbackData, prefix="deckpage"):
    """Renders ``page`` in ``mode``: the arrows keep the mode, the mode-switching rows change it."""

    page: int
    mode: PickerMode = PickerMode.PICK


class NewDeckCallback(CallbackData, prefix="newdeck"):
    """Asks for the name of a deck to create."""


class RemoveDeckCallback(CallbackData, prefix="deckrm"):
    """Asks to delete a deck; ``page`` is where "Cancel" on the confirmation returns to."""

    id: int
    page: int


class ConfirmRemoveDeckCallback(CallbackData, prefix="deckrmok"):
    """Confirms deleting the deck — and every card in it."""

    id: int


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


def deck_keyboard(
    page: DeckPage, selected_deck_id: int | None, mode: PickerMode = PickerMode.PICK
) -> InlineKeyboardMarkup:
    """One button per deck on the page, the selected one marked, plus paging arrows when needed.

    What a deck button does depends on ``mode``: it picks the deck, or in ``DELETE`` mode asks to
    delete it. ``MANAGE`` adds the rows that create a deck and enter ``DELETE`` mode; ``DELETE``
    adds the row back out of it.
    """
    rows = []
    for deck in page.decks:
        text = f"✓ {deck.name}" if deck.id == selected_deck_id else deck.name
        if mode is PickerMode.DELETE:
            data = RemoveDeckCallback(id=deck.id, page=page.page).pack()
        else:
            data = DeckCallback(id=deck.id).pack()
        rows.append([InlineKeyboardButton(text=text, callback_data=data)])

    arrows = []
    if page.has_prev:
        arrows.append(
            InlineKeyboardButton(text="◀", callback_data=DeckPageCallback(page=page.page - 1, mode=mode).pack())
        )
    if page.has_next:
        arrows.append(
            InlineKeyboardButton(text="▶", callback_data=DeckPageCallback(page=page.page + 1, mode=mode).pack())
        )
    if arrows:
        rows.append(arrows)

    if mode is PickerMode.MANAGE:
        rows.append([InlineKeyboardButton(text=NEW_DECK_LABEL, callback_data=NewDeckCallback().pack())])
        if page.decks:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=DELETE_MODE_LABEL,
                        callback_data=DeckPageCallback(page=page.page, mode=PickerMode.DELETE).pack(),
                    )
                ]
            )
    elif mode is PickerMode.DELETE:
        rows.append(
            [
                InlineKeyboardButton(
                    text=BACK_LABEL, callback_data=DeckPageCallback(page=page.page, mode=PickerMode.MANAGE).pack()
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def remove_deck_confirmation_keyboard(deck_id: int, page: int) -> InlineKeyboardMarkup:
    """Delete for real, or go back to the delete-mode page the deck was tapped on."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=CONFIRM_DELETE_LABEL, callback_data=ConfirmRemoveDeckCallback(id=deck_id).pack()
                ),
                InlineKeyboardButton(
                    text=CANCEL_LABEL, callback_data=DeckPageCallback(page=page, mode=PickerMode.DELETE).pack()
                ),
            ]
        ]
    )
