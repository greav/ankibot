"""What a plain message is: a word to look up, or a snippet to distill into cards.

Router-free like ``deck_picker``: the vocabulary-word catch-all and the snippet-cards flow both
read this boundary, and a module owning a ``Router`` cannot be imported by another handler module.
Keeping the threshold here keeps it one number instead of two that drift apart.
"""

MAX_WORD_LENGTH = 64


def plain_text(text: str | None) -> str | None:
    """Normalize a message into usable text, or None when it carries none.

    Rejects empty/whitespace-only text and text starting with "/", so a mistyped command does not
    silently become input.
    """
    if text is None:
        return None
    stripped = text.strip()
    if not stripped or stripped.startswith("/"):
        return None
    return stripped


def word_query(text: str | None) -> str | None:
    """Normalize a message into a word to look up, or None when it carries no usable query.

    Anything over ``MAX_WORD_LENGTH`` is not a word — that is ``snippet_text``'s side of the line.
    """
    stripped = plain_text(text)
    if stripped is None or len(stripped) > MAX_WORD_LENGTH:
        return None
    return stripped


def snippet_text(text: str | None) -> str | None:
    """Normalize a message into a snippet, or None when it reads as a word lookup instead.

    Only text longer than ``MAX_WORD_LENGTH`` qualifies implicitly; a shorter passage reaches the
    snippet flow through /snippet, which accepts any usable length via ``plain_text``.
    """
    stripped = plain_text(text)
    if stripped is None or len(stripped) <= MAX_WORD_LENGTH:
        return None
    return stripped
