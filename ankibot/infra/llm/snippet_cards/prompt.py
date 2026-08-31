"""Prompts for distilling a reading passage into front/back cards.

The response's shape is not built here: ``chat.completions.parse`` derives the strict JSON schema
from the ``CardsAnswer`` model in ``parsing.py``.
"""

import base64

from openai.types.chat import ChatCompletionContentPartParam

from ankibot.application.add_snippet_cards import Snippet, SnippetImage


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


def build_user_content(snippet: Snippet) -> str | list[ChatCompletionContentPartParam]:
    """The user-turn content: the passage's text, or its screenshot as an image part."""
    if snippet.text is not None:
        return snippet.text if snippet.hint is None else f"{snippet.text}\n\nFocus on: {snippet.hint}"
    if snippet.image is not None:
        parts: list[ChatCompletionContentPartParam] = []
        if snippet.hint is not None:
            parts.append({"type": "text", "text": f"Focus on: {snippet.hint}"})
        parts.append({"type": "image_url", "image_url": {"url": image_data_url(snippet.image)}})
        return parts
    msg = "A snippet carries exactly one of text or image"  # Snippet.__post_init__ upholds this.
    raise ValueError(msg)
