"""The word picker decides two things: the callback payload under Telegram's limit, and how the
candidates are laid out."""

from ankibot.presentation.keyboards.word_candidates import (
    CANDIDATES_PER_ROW,
    WordCandidateCallback,
    word_candidates_keyboard,
)

TELEGRAM_CALLBACK_DATA_LIMIT = 64
MAX_CANDIDATES = 6


def test_every_candidate_stays_within_telegrams_callback_data_limit() -> None:
    """Only the index travels, so even the last candidate packs well under 64 bytes."""
    # Act
    packed = WordCandidateCallback(index=MAX_CANDIDATES - 1).pack()

    # Assert
    assert len(packed.encode()) <= TELEGRAM_CALLBACK_DATA_LIMIT


def test_keyboard_can_offer_every_candidate_two_to_a_row() -> None:
    """Each candidate is a button labelled with the word itself, wrapped two per row."""
    # Act
    markup = word_candidates_keyboard(["serendipity", "ubiquitous", "in a nutshell"])

    # Assert
    rows = [[button.text for button in row] for row in markup.inline_keyboard]
    assert rows == [["serendipity", "ubiquitous"], ["in a nutshell"]]
    assert all(len(row) <= CANDIDATES_PER_ROW for row in rows)
