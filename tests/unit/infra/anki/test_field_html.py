from ankibot.infra.anki.field_html import to_field_html


def test_field_html_can_render_each_line_break_as_a_br() -> None:
    """Every newline becomes a ``<br>``, the only line break Anki's card renderer honours."""
    # Act / Assert
    assert to_field_html("one\ntwo\nthree") == "one<br>two<br>three"


def test_field_html_can_keep_plain_text_verbatim() -> None:
    """Text with no markup-like characters and no line breaks passes through unchanged."""
    # Act / Assert
    assert to_field_html('It\'s a "quoted" word; fine.') == 'It\'s a "quoted" word; fine.'


def test_field_html_cannot_let_text_be_read_as_markup() -> None:
    """A bare ``<``, ``>`` or ``&`` in the text is escaped, so Anki shows it instead of parsing it."""
    # Act / Assert
    assert to_field_html("a < b & c > d") == "a &lt; b &amp; c &gt; d"
