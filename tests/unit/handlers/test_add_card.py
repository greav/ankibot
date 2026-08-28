import pytest

from ankibot.presentation.handlers.add_card import card_side


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hello", "hello"),
        ("  hello  ", "hello"),
        ("", None),
        ("   ", None),
        (None, None),
        ("/cancel", None),
    ],
)
def test_card_side_can_normalize_or_reject_input(text: str | None, expected: str | None) -> None:
    """card_side keeps usable text stripped, and rejects empty, whitespace-only or command-like input."""
    # Act
    result = card_side(text)

    # Assert
    assert result == expected
