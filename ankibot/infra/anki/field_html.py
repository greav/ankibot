"""Rendering plain text into an Anki note field.

A field is HTML: what the generators produce is plain text (their prompts forbid markup), so the
one place it is turned into what Anki renders is here, on the way out. A newline collapses to a
space when Anki shows the card, so a line break has to be a ``<br>``; a bare ``<`` or ``&`` would be
read as markup, so the text is escaped first.
"""

import html


def to_field_html(text: str) -> str:
    """Escape ``text`` for an HTML field and render each line break as ``<br>``."""
    return html.escape(text, quote=False).replace("\n", "<br>")
