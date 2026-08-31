import json
import logging
from typing import Any

import httpx2
import pytest
from openai import AsyncOpenAI

from ankibot.application.add_snippet_cards import DraftCard, Snippet, SnippetImage
from ankibot.application.exceptions.generation import CardGenerationError, CardGenerationUnavailableError
from ankibot.infra.llm.snippet_cards.openai_snippet_cards_generator import (
    OpenAISnippetCardsGenerator,
    OpenAISnippetCardsGeneratorConfig,
)
from tests.common.transport import OpenAIHandler, openai_client_for

FAKE_API_KEY = "sk-test-distinctive-s3cr3t-not-real"
TEXT_SNIPPET = Snippet(text="The GIL serializes Python bytecode execution.")


def chat_completion_body(
    *, content: str | None = None, refusal: str | None = None, finish_reason: str = "stop"
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content, "refusal": refusal}
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1_700_000_000,
        "model": "gpt-4o-mini",
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
    }


def cards_content(*cards: tuple[str, str]) -> str:
    return json.dumps({"cards": [{"front": front, "back": back} for front, back in cards]})


def build_handler(
    *, status_code: int = 200, body: dict[str, Any] | None = None, raise_error: Exception | None = None
) -> OpenAIHandler:
    async def handler(request: httpx2.Request) -> httpx2.Response:
        if raise_error is not None:
            raise raise_error
        assert request.url.path == "/v1/chat/completions"
        payload = body if body is not None else chat_completion_body(content=cards_content(("Q", "A")))
        return httpx2.Response(status_code, json=payload)

    return handler


def make_generator(
    handler: OpenAIHandler, *, max_cards: int = 8
) -> tuple[OpenAISnippetCardsGenerator, httpx2.AsyncClient]:
    client = openai_client_for(handler)
    openai_client = AsyncOpenAI(api_key=FAKE_API_KEY, http_client=client, max_retries=0)
    config = OpenAISnippetCardsGeneratorConfig(model="gpt-4o-mini", max_cards=max_cards)
    return OpenAISnippetCardsGenerator(config, openai_client), client


async def test_generator_can_distill_a_text_snippet_with_a_strict_schema() -> None:
    """The request carries the snippet and a strict cards schema, and the answer is parsed into drafts."""
    # Arrange
    requests: list[httpx2.Request] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        body = chat_completion_body(content=cards_content(("What is the GIL?", "A lock"), ("Q2", "A2")))
        return httpx2.Response(200, json=body)

    generator, client = make_generator(handler, max_cards=3)

    # Act
    async with client:
        result = await generator.generate(TEXT_SNIPPET)

    # Assert
    assert result == (DraftCard(front="What is the GIL?", back="A lock"), DraftCard(front="Q2", back="A2"))
    sent = json.loads(requests[0].content)
    assert sent["model"] == "gpt-4o-mini"
    assert "at most 3" in sent["messages"][0]["content"]
    assert sent["messages"][1]["content"] == "The GIL serializes Python bytecode execution."
    json_schema = sent["response_format"]["json_schema"]
    assert json_schema["strict"] is True
    assert json_schema["name"] == "CardsAnswer"
    assert list(json_schema["schema"]["properties"]) == ["cards"]
    assert json_schema["schema"]["additionalProperties"] is False


async def test_generator_can_send_a_screenshot_as_an_image_part() -> None:
    """An image snippet reaches OpenAI as an image_url content part carrying the bytes as a data URL."""
    # Arrange
    requests: list[httpx2.Request] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json=chat_completion_body(content=cards_content(("Q", "A"))))

    generator, client = make_generator(handler)
    snippet = Snippet(image=SnippetImage(data=b"fake-jpeg", mime_type="image/jpeg"), hint="the definition")

    # Act
    async with client:
        await generator.generate(snippet)

    # Assert
    sent = json.loads(requests[0].content)
    parts = sent["messages"][1]["content"]
    assert parts[0] == {"type": "text", "text": "Focus on: the definition"}
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


async def test_generator_cannot_distill_on_a_rate_limit() -> None:
    """A 429 from OpenAI surfaces as CardGenerationUnavailableError, not a raw SDK exception."""
    # Arrange
    handler = build_handler(status_code=429, body={"error": {"message": "rate limited", "type": "rate_limit"}})
    generator, client = make_generator(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationUnavailableError):
            await generator.generate(TEXT_SNIPPET)


async def test_generator_cannot_reach_an_unreachable_openai() -> None:
    """A transport failure surfaces as CardGenerationUnavailableError."""
    # Arrange
    handler = build_handler(raise_error=httpx2.ConnectError("connection refused"))
    generator, client = make_generator(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationUnavailableError):
            await generator.generate(TEXT_SNIPPET)


async def test_generator_cannot_read_a_response_with_non_json_content() -> None:
    """A 200 whose content isn't valid JSON fails as CardGenerationError, not silently."""
    # Arrange
    handler = build_handler(body=chat_completion_body(content="not json"))
    generator, client = make_generator(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationError):
            await generator.generate(TEXT_SNIPPET)


async def test_generator_cannot_read_an_answer_of_the_wrong_shape() -> None:
    """Valid JSON that is not a front/back card list fails as CardGenerationError."""
    # Arrange
    body = chat_completion_body(content=json.dumps({"cards": [{"question": "Q", "answer": "A"}]}))
    handler = build_handler(body=body)
    generator, client = make_generator(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationError):
            await generator.generate(TEXT_SNIPPET)


async def test_generator_cannot_read_a_refusal() -> None:
    """A model refusal is a distinct branch, not a confusing JSON parse failure on None content."""
    # Arrange
    handler = build_handler(body=chat_completion_body(content=None, refusal="cannot help with that"))
    generator, client = make_generator(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationError, match="cannot help with that"):
            await generator.generate(TEXT_SNIPPET)


async def test_generator_cannot_read_a_truncated_answer() -> None:
    """finish_reason == 'length' means truncated JSON, mapped explicitly rather than failing to parse."""
    # Arrange
    handler = build_handler(body=chat_completion_body(content='{"cards": [{"fro', finish_reason="length"))
    generator, client = make_generator(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationError):
            await generator.generate(TEXT_SNIPPET)


async def test_generator_cannot_leak_the_api_key_into_the_logs(caplog: pytest.LogCaptureFixture) -> None:
    """The OpenAI API key never reaches the log stream, even at DEBUG level."""
    # Arrange
    handler = build_handler()
    generator, client = make_generator(handler)

    # Act
    async with client:
        with caplog.at_level(logging.DEBUG):
            await generator.generate(TEXT_SNIPPET)

    # Assert
    assert FAKE_API_KEY not in caplog.text
