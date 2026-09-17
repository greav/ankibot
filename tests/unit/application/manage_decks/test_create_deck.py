"""The deck-name rules ``CreateDeck`` applies before asking AnkiWeb for anything.

The interactor around them is covered through ``/decks``; these are the cases worth a table.
"""

import pytest

from ankibot.application.manage_decks import Deck
from ankibot.application.manage_decks.create_deck import find_deck_named, normalize_deck_name


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("Italian", "Italian"),
        ("  Italian  ", "Italian"),
        (" Spanish :: Verbs ", "Spanish::Verbs"),
        ("A::B::C", "A::B::C"),
    ],
)
def test_user_can_name_a_deck_the_way_anki_stores_it(typed: str, expected: str) -> None:
    """Surrounding whitespace goes, and each ``::`` level is trimmed as Anki would trim it."""
    # Act / Assert
    assert normalize_deck_name(typed) == expected


@pytest.mark.parametrize("typed", ["", "   ", "::", "Spanish::", "::Verbs", "Spanish:: ::Verbs"])
def test_user_cannot_name_a_deck_with_a_blank_level(typed: str) -> None:
    """A name with nothing in it, or an empty nesting level, names no deck rather than a guessed one."""
    # Act / Assert
    assert normalize_deck_name(typed) is None


def test_user_cannot_duplicate_a_deck_by_changing_its_case() -> None:
    """Anki deck names are unique ignoring case, so ``spanish`` finds ``Spanish``."""
    # Arrange
    decks = [Deck(id=1, name="Default"), Deck(id=2, name="Spanish")]

    # Act / Assert
    assert find_deck_named(decks, "spanish") == Deck(id=2, name="Spanish")
    assert find_deck_named(decks, "Italian") is None
