"""Prompts for distilling a reading passage into front/back cards.

The response's shape is not built here: ``chat.completions.parse`` derives the strict JSON schema
from the ``CardsAnswer`` model in ``parsing.py``.
"""

import base64
from collections.abc import Sequence

from openai.types.chat import ChatCompletionContentPartParam

from ankibot.application.add_snippet_cards import DraftCard, Snippet, SnippetImage


def build_system_prompt(max_cards: int) -> str:
    """The system-turn prompt asking for at most ``max_cards`` cards grounded in the passage."""
    return (
        "You turn a passage a learner is reading into Anki flashcards for spaced repetition. "
        f"Create at most {max_cards} front/back cards — fewer when the passage holds fewer facts "
        "worth memorizing, and none when it holds none. Each card is atomic: the front asks about "
        "exactly one fact, the back answers it briefly. Use only what the passage itself states — "
        "never add outside knowledge. Write the cards in the passage's own language. Reply with "
        "plain text only in every field — no HTML and no Markdown formatting, since the values are "
        "stored and shown verbatim."
    )


def image_data_url(image: SnippetImage) -> str:
    """``image`` as the ``data:`` URL an OpenAI image part carries."""
    encoded = base64.b64encode(image.data).decode("ascii")
    return f"data:{image.mime_type};base64,{encoded}"


def kept_cards_note(kept: Sequence[DraftCard]) -> str:
    """The instruction listing the cards the learner already kept, so the model covers other facts."""
    listed = "\n".join(f"- {card.front} — {card.back}" for card in kept)
    return f"The learner already kept these cards from this passage. Do not repeat them; cover other facts:\n{listed}"


def build_user_content(snippet: Snippet, kept: Sequence[DraftCard] = ()) -> str | list[ChatCompletionContentPartParam]:
    """The user-turn content: the passage's text, or its screenshot as an image part.

    The hint, and then the kept cards when there are any, follow the passage as further instructions.
    """
    notes = []
    if snippet.hint is not None:
        notes.append(f"Focus on: {snippet.hint}")
    if kept:
        notes.append(kept_cards_note(kept))

    if snippet.text is not None:
        return "\n\n".join([snippet.text, *notes])
    if snippet.image is not None:
        parts: list[ChatCompletionContentPartParam] = [{"type": "text", "text": note} for note in notes]
        parts.append({"type": "image_url", "image_url": {"url": image_data_url(snippet.image)}})
        return parts
    msg = "A snippet carries exactly one of text or image"  # Snippet.__post_init__ upholds this.
    raise ValueError(msg)
