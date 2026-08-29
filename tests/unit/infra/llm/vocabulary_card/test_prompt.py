import logging

import pytest

from ankibot.domain.card_template import CardTemplate
from ankibot.infra.llm.vocabulary_card.prompt import build_user_prompt, response_schema


def test_response_schema_can_declare_every_field_as_required_and_a_string() -> None:
    """The schema's properties and required list are exactly the template's fields, in order."""
    # Arrange
    template = CardTemplate(name="English Words V2", fields=("Word", "Meaning", "Example"))

    # Act
    schema = response_schema(template)

    # Assert
    assert list(schema["properties"]) == ["Word", "Meaning", "Example"]
    assert schema["required"] == ["Word", "Meaning", "Example"]
    assert schema["additionalProperties"] is False
    assert all(field["type"] == "string" for field in schema["properties"].values())


def test_response_schema_can_carry_field_names_with_spaces_and_non_ascii() -> None:
    """A field name outside FIELD_HINTS still survives as a valid JSON property key."""
    # Arrange
    template = CardTemplate(name="Custom", fields=("Example Sentence", "Перевод"))

    # Act
    schema = response_schema(template)

    # Assert
    assert set(schema["properties"]) == {"Example Sentence", "Перевод"}
    assert schema["required"] == ["Example Sentence", "Перевод"]


def test_response_schema_can_attach_a_hint_as_a_description() -> None:
    """A field matching FIELD_HINTS carries its hint as the property's description."""
    # Arrange
    template = CardTemplate(name="English Words V2", fields=("Word", "Custom Field"))

    # Act
    schema = response_schema(template)

    # Assert
    assert schema["properties"]["Word"]["description"] == "the headword, lowercase"
    assert "description" not in schema["properties"]["Custom Field"]


def test_response_schema_can_match_a_hint_regardless_of_case_or_whitespace() -> None:
    """A field differing from FIELD_HINTS only in case or surrounding whitespace still matches."""
    # Arrange
    template = CardTemplate(name="English Words V2", fields=(" word ", "MEANING"))

    # Act
    schema = response_schema(template)

    # Assert
    assert schema["properties"][" word "]["description"] == "the headword, lowercase"
    assert schema["properties"]["MEANING"]["description"] == "short English definition, under 12 words"


def test_response_schema_can_reorder_without_changing_anything_else() -> None:
    """Reordering the template's fields reorders the schema and changes nothing else."""
    # Arrange
    forward = CardTemplate(name="English Words V2", fields=("Word", "Meaning", "Example"))
    reversed_template = CardTemplate(name="English Words V2", fields=("Example", "Meaning", "Word"))

    # Act
    forward_schema = response_schema(forward)
    reversed_schema = response_schema(reversed_template)

    # Assert
    assert list(forward_schema["properties"]) == ["Word", "Meaning", "Example"]
    assert list(reversed_schema["properties"]) == ["Example", "Meaning", "Word"]
    assert forward_schema["properties"] == reversed_schema["properties"]


def test_response_schema_can_warn_about_an_orphaned_hint(caplog: pytest.LogCaptureFixture) -> None:
    """A FIELD_HINTS entry matching no field of the current template logs a warning naming it."""
    # Arrange
    template = CardTemplate(name="Renamed", fields=("Headword",))

    # Act
    with caplog.at_level(logging.WARNING):
        response_schema(template)

    # Assert
    assert "Word" in caplog.text


def test_build_user_prompt_can_carry_the_word() -> None:
    """The user prompt names the word to fill a card for."""
    # Arrange
    template = CardTemplate(name="English Words V2", fields=("Word", "Meaning"))

    # Act
    prompt = build_user_prompt("serendipity", template)

    # Assert
    assert "serendipity" in prompt
