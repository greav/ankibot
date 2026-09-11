import base64

from ankibot.application.add_snippet_cards import DraftCard, Snippet, SnippetImage
from ankibot.infra.llm.snippet_cards.prompt import build_system_prompt, build_user_content

PNG_BYTES = b"\x89PNG-not-really"
KEPT = (DraftCard(front="What is the GIL?", back="A lock"), DraftCard(front="Q2", back="A2"))


def test_system_prompt_can_carry_the_card_cap() -> None:
    """The cap the config sets reaches the model as part of the instruction."""
    # Act
    result = build_system_prompt(5)

    # Assert
    assert "at most 5" in result


def test_user_content_can_be_the_snippet_text_itself() -> None:
    """A text snippet travels as the plain user turn, with the hint appended when there is one."""
    # Act / Assert
    assert build_user_content(Snippet(text="The GIL serializes bytecode.")) == "The GIL serializes bytecode."
    assert build_user_content(Snippet(text="The GIL serializes bytecode.", hint="locks only")) == (
        "The GIL serializes bytecode.\n\nFocus on: locks only"
    )


def test_user_content_can_list_the_kept_cards_after_the_text() -> None:
    """The kept cards reach the model as an instruction not to repeat them, after the hint."""
    # Act
    result = build_user_content(Snippet(text="The GIL serializes bytecode.", hint="locks only"), KEPT)

    # Assert
    assert result == (
        "The GIL serializes bytecode.\n\nFocus on: locks only\n\n"
        "The learner already kept these cards from this passage. Do not repeat them; cover other facts:\n"
        "- What is the GIL? — A lock\n- Q2 — A2"
    )


def test_user_content_can_list_the_kept_cards_alongside_a_screenshot() -> None:
    """With an image snippet the kept cards travel as a text part before the image."""
    # Arrange
    snippet = Snippet(image=SnippetImage(data=PNG_BYTES, mime_type="image/png"))

    # Act
    result = build_user_content(snippet, KEPT)

    # Assert
    assert isinstance(result, list)
    assert result[0]["type"] == "text"
    assert result[0]["text"].endswith("- What is the GIL? — A lock\n- Q2 — A2")
    assert result[1]["type"] == "image_url"


def test_user_content_can_carry_a_screenshot_as_a_data_url() -> None:
    """An image snippet becomes an image part whose data URL holds the exact bytes, base64-encoded."""
    # Arrange
    snippet = Snippet(image=SnippetImage(data=PNG_BYTES, mime_type="image/png"))

    # Act
    result = build_user_content(snippet)

    # Assert
    encoded = base64.b64encode(PNG_BYTES).decode("ascii")
    assert result == [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}]


def test_user_content_can_put_the_caption_hint_before_the_screenshot() -> None:
    """A photo caption reaches the model as a text part alongside the image."""
    # Arrange
    snippet = Snippet(image=SnippetImage(data=PNG_BYTES, mime_type="image/jpeg"), hint="the definition")

    # Act
    result = build_user_content(snippet)

    # Assert
    assert isinstance(result, list)
    assert result[0] == {"type": "text", "text": "Focus on: the definition"}
    assert result[1]["type"] == "image_url"
