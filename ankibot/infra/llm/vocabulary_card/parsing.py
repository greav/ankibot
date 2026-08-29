import json

from pydantic import TypeAdapter, ValidationError

from ankibot.application.exceptions.generation import CardGenerationError

_FIELDS_ADAPTER = TypeAdapter(dict[str, str])


def parse_fields(raw: str) -> dict[str, str]:
    """Parse ``raw`` into a field-name → value mapping, or raise ``CardGenerationError``."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as decode_error:
        raise CardGenerationError("The card generator's answer was not valid JSON") from decode_error

    try:
        return _FIELDS_ADAPTER.validate_python(data)
    except ValidationError as validation_error:
        raise CardGenerationError(
            "The card generator's answer was not a flat object of string values"
        ) from validation_error
