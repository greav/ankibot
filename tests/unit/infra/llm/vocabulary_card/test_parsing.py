import pytest

from ankibot.application.exceptions.generation import CardGenerationError
from ankibot.infra.llm.vocabulary_card.parsing import parse_fields


def test_parse_fields_can_read_a_well_formed_body() -> None:
    """A flat JSON object of strings parses into the same mapping."""
    # Act
    result = parse_fields('{"Word": "hello", "Meaning": "a greeting"}')

    # Assert
    assert result == {"Word": "hello", "Meaning": "a greeting"}


def test_parse_fields_cannot_read_invalid_json() -> None:
    """Text that isn't JSON at all fails as a CardGenerationError, not a raw JSONDecodeError."""
    # Act / Assert
    with pytest.raises(CardGenerationError):
        parse_fields("not json")


def test_parse_fields_cannot_read_a_json_array() -> None:
    """Valid JSON that isn't an object fails, since it can't be a field mapping."""
    # Act / Assert
    with pytest.raises(CardGenerationError):
        parse_fields('["Word", "Meaning"]')


def test_parse_fields_cannot_read_a_non_string_value() -> None:
    """A value that isn't a string fails, since Anki fields are text."""
    # Act / Assert
    with pytest.raises(CardGenerationError):
        parse_fields('{"Word": "hello", "Meaning": 42}')
