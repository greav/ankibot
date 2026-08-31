from ankibot.presentation.handlers.vocabulary_card import format_card_preview


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
