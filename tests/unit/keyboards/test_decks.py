"""The deck picker's paging rule, tested directly rather than through a rendered keyboard.

``page_of`` is the one thing in the keyboard that decides something; the rest is a static markup.
"""

import pytest

from ankibot.application.manage_decks import Deck
from ankibot.presentation.keyboards.decks import DECK_PAGE_SIZE, DeckCallback, page_of

TELEGRAM_CALLBACK_DATA_LIMIT = 64
MAX_INT64 = 2**63 - 1


def make_decks(count: int) -> list[Deck]:
    """Build ``count`` decks named after their position, so a slice is readable in a failure."""
    return [Deck(id=index, name=f"deck-{index}") for index in range(count)]


@pytest.mark.parametrize(
    ("count", "requested_page", "expected_page", "expected_names", "has_prev", "has_next"),
    [
        (0, 0, 0, [], False, False),
        (3, 0, 0, ["deck-0", "deck-1", "deck-2"], False, False),
        (16, 0, 0, [f"deck-{index}" for index in range(8)], False, True),
        (16, 1, 1, [f"deck-{index}" for index in range(8, 16)], True, False),
        (10, 1, 1, ["deck-8", "deck-9"], True, False),
        (10, -3, 0, [f"deck-{index}" for index in range(8)], False, True),
        (10, 99, 1, ["deck-8", "deck-9"], True, False),
    ],
)
def test_user_can_page_through_any_number_of_decks(
    count: int,
    requested_page: int,
    expected_page: int,
    expected_names: list[str],
    has_prev: bool,
    has_next: bool,
) -> None:
    """Any requested page lands inside the list, with arrows matching the neighbours that exist."""
    # Arrange
    decks = make_decks(count)

    # Act
    page = page_of(decks, requested_page)

    # Assert
    assert [deck.name for deck in page.decks] == expected_names
    assert page.page == expected_page
    assert page.has_prev is has_prev
    assert page.has_next is has_next


def test_user_can_page_a_list_that_exactly_fills_a_page() -> None:
    """An exact multiple of the page size does not offer a next page holding nothing."""
    # Arrange / Act
    page = page_of(make_decks(DECK_PAGE_SIZE), 0)

    # Assert
    assert len(page.decks) == DECK_PAGE_SIZE
    assert page.has_next is False


def test_user_cannot_overflow_telegrams_callback_data_limit() -> None:
    """Even the largest deck id AnkiWeb can hand out fits Telegram's 64-byte callback_data."""
    # Arrange / Act
    packed = DeckCallback(id=MAX_INT64).pack()

    # Assert
    assert len(packed.encode()) <= TELEGRAM_CALLBACK_DATA_LIMIT
