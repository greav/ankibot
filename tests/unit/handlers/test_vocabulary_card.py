import pytest

from ankibot.presentation.handlers.vocabulary_card import MAX_WORD_LENGTH, format_card_preview, word_query


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hello", "hello"),
        ("  hello  ", "hello"),
        ("", None),
        ("   ", None),
        (None, None),
        ("/cancel", None),
        ("a" * MAX_WORD_LENGTH, "a" * MAX_WORD_LENGTH),
        ("a" * (MAX_WORD_LENGTH + 1), None),
    ],
)
def test_word_query_can_normalize_or_reject_input(text: str | None, expected: str | None) -> None:
    """word_query keeps usable text stripped, and rejects empty, command-like or over-length input."""
    # Act
    result = word_query(text)

    # Assert
    assert result == expected


def test_format_card_preview_can_render_every_field_in_order() -> None:
    """The preview names the deck and lists every field, in the order the caller passed them."""
    # Arrange
    fields = [("Word", "serendipity"), ("Meaning", "a pleasant surprise"), ("Example", "What a serendipity!")]

    # Act
    result = format_card_preview("English Words V2", fields)

    # Assert
    assert result == (
        "Add to English Words V2?\n\nWord: serendipity\nMeaning: a pleasant surprise\nExample: What a serendipity!"
    )
