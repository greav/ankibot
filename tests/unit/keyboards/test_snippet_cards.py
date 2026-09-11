"""The snippet-cards keyboard decides three things: the callback payload under Telegram's limit,
which cards read as selected, and how many toggles share a row. ``toggled`` is the selection's
transition rule, tested as a plain function.
"""

from ankibot.presentation.keyboards.snippet_cards import (
    TOGGLES_PER_ROW,
    SnippetCardCallback,
    regenerate_label,
    snippet_cards_keyboard,
    toggled,
)

TELEGRAM_CALLBACK_DATA_LIMIT = 64
MAX_CARDS = 8


def button_texts(selection: list[bool]) -> list[list[str]]:
    """The keyboard's rows as their button labels, so a failure reads as what the user would see."""
    return [[button.text for button in row] for row in snippet_cards_keyboard(selection).inline_keyboard]


def test_every_action_stays_within_telegrams_callback_data_limit() -> None:
    """Each action, toggle at the largest index included, packs under the 64-byte callback_data limit."""
    # Arrange / Act
    packed = [
        SnippetCardCallback(action="toggle", index=MAX_CARDS - 1).pack(),
        *(
            SnippetCardCallback(action=action).pack()
            for action in ("save", "regenerate", "feedback", "cancel", "deck")
        ),
    ]

    # Assert
    assert all(len(data.encode()) <= TELEGRAM_CALLBACK_DATA_LIMIT for data in packed)


def test_keyboard_can_mark_selected_and_unselected_cards() -> None:
    """Each toggle carries the card's preview number and its state; Save and Regenerate count their cards."""
    # Act
    rows = button_texts([True, False, True])

    # Assert
    assert rows == [
        ["☑ 1", "☐ 2", "☑ 3"],
        ["Save 2 of 3", "Cancel"],
        ["Regenerate 1", "Regenerate with feedback"],
        ["Change deck"],
    ]


def test_regenerate_label_can_say_it_replaces_the_whole_batch() -> None:
    """With nothing unticked Regenerate carries no count: there is nothing to keep apart."""
    # Act / Assert
    assert regenerate_label([True, True]) == "Regenerate"
    assert regenerate_label([False, False]) == "Regenerate 2"


def test_keyboard_cannot_put_more_than_four_toggles_in_a_row() -> None:
    """A full batch of eight wraps into two rows of four, the action rows still last."""
    # Act
    rows = button_texts([True] * MAX_CARDS)

    # Assert
    assert [len(row) for row in rows[:-3]] == [TOGGLES_PER_ROW, TOGGLES_PER_ROW]
    assert rows[-3:] == [["Save 8 of 8", "Cancel"], ["Regenerate", "Regenerate with feedback"], ["Change deck"]]


def test_toggled_can_flip_one_card() -> None:
    """Toggling flips exactly the tapped card and leaves the others as they were."""
    # Act
    result = toggled([True, True, False], 1)

    # Assert
    assert result == (True, False, False)


def test_toggled_cannot_change_selection_for_an_index_out_of_range() -> None:
    """A tap carrying an index the batch never had is a no-op, not a crash."""
    # Act / Assert
    assert toggled([True, False], 2) == (True, False)
    assert toggled([True, False], -1) == (True, False)
