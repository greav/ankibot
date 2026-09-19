import logging
from typing import Any

from openai.types.chat import ChatCompletionContentPartParam

from ankibot.application.add_vocabulary_word import CardFeedback
from ankibot.application.common.dto.image import Image
from ankibot.domain.card_template import CardTemplate
from ankibot.infra.llm.images import image_data_url

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You fill the fields of an Anki flashcard for a single English vocabulary entry an "
    "intermediate-to-advanced learner whose first language is Russian wants to study. The entry "
    "may be a word, a phrasal verb, an idiom or a collocation: treat the whole expression as one "
    "unit and never split it into its parts. The fields feed two cards: one showing the entry and "
    "asking for its meaning, one showing the Russian translations and an example with the entry "
    "blanked out and asking for the entry — so the translations must be specific enough to call "
    "this entry to mind rather than a near-synonym, and what sets it apart from its near-synonyms "
    "matters more than a long list of them. Keep every field as short as it can be while staying "
    "exact: many short lines beat one paragraph. Reply with plain text only in every field — no "
    "HTML and no Markdown formatting, "
    "since the values are stored and shown verbatim. When a field holds several items — "
    "sentences, situations, senses — put each on its own line, never run them together in one "
    "paragraph."
)

CONTEXT_NOTE = (
    "The entry appears in the attached screenshot; ground the fields that quote its usage in the "
    "sentence it appears in there, and define first the sense it carries there."
)


def build_user_prompt(
    word: str, template: CardTemplate, feedback: CardFeedback | None = None, *, with_context: bool = False
) -> str:
    """The user-turn prompt asking the model to fill ``template``'s fields for ``word``.

    With ``feedback``, the card the learner was shown and their note on it follow the request, so
    the redo is about that card rather than a fresh guess. ``with_context`` adds the instruction to
    read the word's usage off the screenshot sent alongside.
    """
    fields = ", ".join(template.fields)
    parts = [f'Fill the fields ({fields}) of a flashcard for the English entry "{word}".']
    if with_context:
        parts.append(CONTEXT_NOTE)
    if feedback is not None:
        previous = "\n".join(f"{name}: {value}" for name, value in feedback.previous.items())
        parts.append(
            f"The learner was shown this card:\n{previous}\nThe learner asked to change this about it: {feedback.note}"
        )
    return "\n\n".join(parts)


def build_user_content(
    word: str, template: CardTemplate, context: Image | None = None, feedback: CardFeedback | None = None
) -> str | list[ChatCompletionContentPartParam]:
    """The user-turn content: the prompt alone, or the prompt as a text part followed by the screenshot."""
    if context is None:
        return build_user_prompt(word, template, feedback)
    return [
        {"type": "text", "text": build_user_prompt(word, template, feedback, with_context=True)},
        {"type": "image_url", "image_url": {"url": image_data_url(context)}},
    ]


# What each field is for. A discovered field with no entry is described by its name alone.
# TODO: this dict may be removable. Anki carries a per-field description in
# Notetype.Field.Config.description (proto/ankiweb/common.proto), and get-notetype-fields
# returns the whole Notetype.Field including config — so the hints could be read from the
# notetype itself, leaving AnkiWeb the single source of truth for names, order and meaning
# alike, with nothing left to drift. Unverified: whether AnkiWeb actually populates that
# field or returns it empty. Then either read it in AnkiWebVocabularyCardGateway.target() and delete this dict,
# or keep this and note here that the field comes back empty.
FIELD_HINTS = {
    "Word": "the headword, lowercase; a phrasal verb, idiom or collocation stays whole",
    "Definition": "a short plain-English definition per sense, one sense per line, numbered when there are several",
    "Part of Speech": "the parts of speech, separated by semicolons",
    "Synonyms": (
        "a few close synonyms separated by semicolons, each followed in parentheses by how the "
        "headword differs from it"
    ),
    "Situations to Use It": (
        "when a learner would reach for this word, one situation per line, naming the register "
        "(formal, informal, technical) when it is not neutral"
    ),
    "Russian Translations": (
        "translations separated by semicolons, in the order of the senses, specific enough to "
        "call this word to mind rather than a near-synonym"
    ),
    "Example Sentences": (
        "two or three short natural sentences, one per line, one more for each further sense; "
        "each shows a different sense or a different collocation"
    ),
    "IPA": "IPA transcription, one per line when the readings differ",
    "Example with Blank": (
        "the first example sentence with the entry replaced by ___, one ___ per word of the entry; "
        "the front of the card that asks the learner to produce the entry"
    ),
    "Collocations": (
        "the most frequent phrases the word forms, separated by semicolons, each as the whole "
        "phrase a learner would say (heavily dependent on; make a decision)"
    ),
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
