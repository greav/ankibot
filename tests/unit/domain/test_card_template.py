from ankibot.domain.card_template import CardTemplate, in_template_order, missing_fields

TEMPLATE = CardTemplate(name="English Words V2", fields=("Word", "Meaning", "Example"))


def test_missing_fields_can_report_every_unfilled_field() -> None:
    """A field absent from values or blank after stripping counts as missing; a filled one does not."""
    # Arrange
    values = {"Word": "hello", "Meaning": "   ", "Extra": "ignored"}

    # Act
    result = missing_fields(TEMPLATE, values)

    # Assert
    assert result == ("Meaning", "Example")


def test_missing_fields_reports_nothing_when_every_field_is_filled() -> None:
    """A complete, non-blank mapping reports no missing fields."""
    # Arrange
    values = {"Word": "hello", "Meaning": "a greeting", "Example": "Hello there!"}

    # Act
    result = missing_fields(TEMPLATE, values)

    # Assert
    assert result == ()


def test_in_template_order_can_reorder_and_drop_extras() -> None:
    """Values come back ordered as the template lists its fields, with keys outside it dropped."""
    # Arrange
    values = {"Extra": "dropped", "Example": "Hello there!", "Word": "hello", "Meaning": "a greeting"}

    # Act
    result = in_template_order(TEMPLATE, values)

    # Assert
    assert result == ("hello", "a greeting", "Hello there!")


def test_in_template_order_can_drop_a_field_missing_from_values() -> None:
    """A template field absent from values is simply skipped, not padded with a placeholder."""
    # Arrange
    values = {"Word": "hello", "Example": "Hello there!"}

    # Act
    result = in_template_order(TEMPLATE, values)

    # Assert
    assert result == ("hello", "Hello there!")
