"""``clean_candidates`` decides which of the model's words reach the picker; ``execute`` around it
is covered through the handler."""

from ankibot.application.add_vocabulary_word.suggest_words import clean_candidates


def test_clean_can_strip_and_keep_reading_order() -> None:
    """Candidates come back trimmed, in the order the model listed them."""
    # Act / Assert
    assert clean_candidates(["  serendipity ", "ubiquitous\n"]) == ("serendipity", "ubiquitous")


def test_clean_cannot_offer_a_blank_or_a_repeated_word() -> None:
    """Blanks are dropped, and a word repeated in another case is offered once, as first written."""
    # Act
    result = clean_candidates(["Serendipity", "", "   ", "serendipity", "SERENDIPITY", "ubiquitous"])

    # Assert
    assert result == ("Serendipity", "ubiquitous")
