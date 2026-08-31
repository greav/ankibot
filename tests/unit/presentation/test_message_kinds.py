import pytest

from ankibot.presentation.message_kinds import MAX_WORD_LENGTH, plain_text, snippet_text, word_query


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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a" * (MAX_WORD_LENGTH + 1), "a" * (MAX_WORD_LENGTH + 1)),
        ("  " + "a" * (MAX_WORD_LENGTH + 1) + "  ", "a" * (MAX_WORD_LENGTH + 1)),
        ("a" * MAX_WORD_LENGTH, None),
        ("hello", None),
        ("", None),
        (None, None),
        ("/" + "a" * (MAX_WORD_LENGTH + 1), None),
    ],
)
def test_snippet_text_can_claim_only_what_is_not_a_word(text: str | None, expected: str | None) -> None:
    """snippet_text takes text past the word-length line and nothing on or below it, so the two flows never overlap."""
    # Act
    result = snippet_text(text)

    # Assert
    assert result == expected


def test_every_usable_text_is_either_a_word_or_a_snippet() -> None:
    """The classifiers split plain_text's domain exactly in two — no text is claimed by both or by neither."""
    # Arrange
    samples = ["hello", "a" * MAX_WORD_LENGTH, "a" * (MAX_WORD_LENGTH + 1), "  padded  ", "a" * 500]

    # Act / Assert
    for text in samples:
        assert plain_text(text) is not None
        claims = [word_query(text) is not None, snippet_text(text) is not None]
        assert claims.count(True) == 1
