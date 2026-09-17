from aiogram.types import MessageEntity

from ankibot.presentation.handlers.vocabulary_card import format_card_preview


def test_format_card_preview_can_render_every_field_in_order() -> None:
    """The preview names the deck and lists every field, in the order the caller passed them."""
    # Arrange
    fields = [("Word", "serendipity"), ("Meaning", "a pleasant surprise"), ("Example", "What a serendipity!")]

    # Act
    text, _ = format_card_preview("English Words V2", fields).render()

    # Assert
    assert text == (
        "Add to English Words V2?\n\nWord\nserendipity\n\nMeaning\na pleasant surprise\n\nExample\nWhat a serendipity!"
    )


def test_format_card_preview_can_bold_every_field_name_and_nothing_else() -> None:
    """Field names arrive as bold entities over the plain text; the values stay unformatted."""
    # Arrange
    fields = [("Word", "serendipity"), ("Meaning", "a pleasant surprise")]

    # Act
    text, entities = format_card_preview("Deck", fields).render()

    # Assert
    assert [text[entity.offset : entity.offset + entity.length] for entity in entities] == ["Word", "Meaning"]
    assert all(entity.type == "bold" for entity in entities)


def test_format_card_preview_cannot_let_a_value_be_parsed_as_markup() -> None:
    """A value carrying markup-like characters reaches the text verbatim, with no parse mode set."""
    # Arrange
    fields = [("Word", "<b>&amp;</b> *_`")]

    # Act
    kwargs = format_card_preview("Deck", fields).as_kwargs()

    # Assert
    assert kwargs["text"] == "Add to Deck?\n\nWord\n<b>&amp;</b> *_`"
    assert kwargs["parse_mode"] is None
    assert kwargs["entities"] == [MessageEntity(type="bold", offset=14, length=4)]
