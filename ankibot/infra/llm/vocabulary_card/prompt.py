import logging
from typing import Any

from ankibot.domain.card_template import CardTemplate

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You fill the fields of an Anki flashcard for a single English vocabulary word a language "
    "learner wants to study. Reply with plain text only in every field — no HTML and no Markdown "
    "formatting, since the values are stored and shown verbatim."
)


def build_user_prompt(word: str, template: CardTemplate) -> str:
    """The user-turn prompt asking the model to fill ``template``'s fields for ``word``."""
    fields = ", ".join(template.fields)
    return f'Fill the fields ({fields}) of a flashcard for the English word "{word}".'


# What each field is for. A discovered field with no entry is described by its name alone.
# TODO: this dict may be removable. Anki carries a per-field description in
# Notetype.Field.Config.description (proto/ankiweb/common.proto), and get-notetype-fields
# returns the whole Notetype.Field including config — so the hints could be read from the
# notetype itself, leaving AnkiWeb the single source of truth for names, order and meaning
# alike, with nothing left to drift. Unverified: whether AnkiWeb actually populates that
# field or returns it empty. Then either read it in AnkiWebVocabularyCardGateway.target() and delete this dict,
# or keep this and note here that the field comes back empty.
FIELD_HINTS = {
    "Word": "the headword, lowercase",
    "Meaning": "short English definition, under 12 words",
    "Example": "one natural sentence using the word",
}

_HINTS = {name.strip().casefold(): hint for name, hint in FIELD_HINTS.items()}


def hint_for(field: str) -> str | None:
    """The hint for ``field``, matched case- and whitespace-insensitively, or None when there is none."""
    return _HINTS.get(field.strip().casefold())


def response_schema(template: CardTemplate) -> dict[str, Any]:
    """The strict JSON schema for one filled card: one string per template field, nothing else."""
    matched = {field.strip().casefold() for field in template.fields}
    orphaned = [name for name in FIELD_HINTS if name.strip().casefold() not in matched]
    if orphaned:
        logger.warning("FIELD_HINTS has entries matching no field of the current template: %s", ", ".join(orphaned))

    return {
        "type": "object",
        "properties": {
            field: {"type": "string"} | ({"description": hint} if (hint := hint_for(field)) else {})
            for field in template.fields
        },
        "required": list(template.fields),
        "additionalProperties": False,
    }
