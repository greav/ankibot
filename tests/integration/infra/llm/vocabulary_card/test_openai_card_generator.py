import json
import logging
from typing import Any

import httpx2
import pytest
from openai import AsyncOpenAI

from ankibot.application.add_vocabulary_word import CardFeedback
from ankibot.application.common.dto.image import Image
from ankibot.application.common.model_catalog import ModelOption
from ankibot.application.exceptions.generation import CardGenerationError, CardGenerationUnavailableError
from ankibot.domain.card_template import CardTemplate
from ankibot.infra.llm.vocabulary_card.openai_card_generator import OpenAICardGenerator
from tests.common.transport import OpenAIHandler, openai_client_for

FAKE_API_KEY = "sk-test-distinctive-s3cr3t-not-real"
MODEL = ModelOption(id="gpt-4o-mini", label="GPT-4o mini")
TEMPLATE = CardTemplate(name="English Words V2", fields=("Word", "Meaning", "Example"))


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


def build_handler(
    *, status_code: int = 200, body: dict[str, Any] | None = None, raise_error: Exception | None = None
) -> OpenAIHandler:
    async def handler(request: httpx2.Request) -> httpx2.Response:
        if raise_error is not None:
            raise raise_error
        assert request.url.path == "/v1/chat/completions"
        payload = body if body is not None else chat_completion_body(content='{"Word": "hello"}')
        return httpx2.Response(status_code, json=payload)

    return handler


def make_generator(handler: OpenAIHandler) -> tuple[OpenAICardGenerator, httpx2.AsyncClient]:
    client = openai_client_for(handler)
    openai_client = AsyncOpenAI(api_key=FAKE_API_KEY, http_client=client, max_retries=0)
    generator = OpenAICardGenerator(openai_client)
    return generator, client


async def test_generator_can_ask_for_a_redo_with_the_learners_note() -> None:
    """Feedback reaches OpenAI in the user turn, with the card it is about."""
    # Arrange
    requests: list[httpx2.Request] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        body = chat_completion_body(content=json.dumps({"Word": "hello", "Meaning": "a greeting", "Example": "Hi!"}))
        return httpx2.Response(200, json=body)

    generator, client = make_generator(handler)
    feedback = CardFeedback(note="shorter example", previous={"Word": "hello", "Meaning": "hi", "Example": "Hello!"})

    # Act
    async with client:
        await generator.generate("hello", TEMPLATE, model=MODEL, feedback=feedback)

    # Assert
    sent = json.loads(requests[0].content)
    user_turn = sent["messages"][1]["content"]
    assert "Example: Hello!" in user_turn
    assert user_turn.endswith("shorter example")


async def test_generator_can_send_the_screenshot_context_as_an_image_part() -> None:
    """A screenshot context reaches OpenAI as an image_url part after the prompt text."""
    # Arrange
    requests: list[httpx2.Request] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        body = chat_completion_body(content=json.dumps({"Word": "hello", "Meaning": "hi", "Example": "Hello!"}))
        return httpx2.Response(200, json=body)

    generator, client = make_generator(handler)

    # Act
    async with client:
        screenshot = Image(data=b"fake-jpeg", mime_type="image/jpeg")
        await generator.generate("hello", TEMPLATE, model=MODEL, context=screenshot)

    # Assert
    parts = json.loads(requests[0].content)["messages"][1]["content"]
    assert parts[0]["type"] == "text"
    assert 'the English entry "hello"' in parts[0]["text"]
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


async def test_generator_can_fill_a_card_with_a_strict_schema() -> None:
    """The request carries a strict json_schema built from the template, and the answer is parsed."""
    # Arrange
    requests: list[httpx2.Request] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        body = chat_completion_body(content=json.dumps({"Word": "hello", "Meaning": "hi", "Example": "Hello!"}))
        return httpx2.Response(200, json=body)

    generator, client = make_generator(handler)

    # Act
    async with client:
        result = await generator.generate("hello", TEMPLATE, model=MODEL)

    # Assert
    assert result == {"Word": "hello", "Meaning": "hi", "Example": "Hello!"}
    sent = json.loads(requests[0].content)
    assert sent["model"] == MODEL.id
    assert "hello" in sent["messages"][1]["content"]
    json_schema = sent["response_format"]["json_schema"]
    assert json_schema["strict"] is True
    assert list(json_schema["schema"]["properties"]) == ["Word", "Meaning", "Example"]


async def test_generator_cannot_fill_a_card_on_a_rate_limit() -> None:
    """A 429 from OpenAI surfaces as CardGenerationUnavailableError, not a raw SDK exception."""
    # Arrange
    handler = build_handler(status_code=429, body={"error": {"message": "rate limited", "type": "rate_limit"}})
    generator, client = make_generator(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationUnavailableError):
            await generator.generate("hello", TEMPLATE, model=MODEL)


async def test_generator_cannot_fill_a_card_on_a_server_error() -> None:
    """A 500 from OpenAI surfaces as CardGenerationUnavailableError."""
    # Arrange
    handler = build_handler(status_code=500, body={"error": {"message": "boom", "type": "server_error"}})
    generator, client = make_generator(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationUnavailableError):
            await generator.generate("hello", TEMPLATE, model=MODEL)


async def test_generator_cannot_reach_an_unreachable_openai() -> None:
    """A transport failure surfaces as CardGenerationUnavailableError."""
    # Arrange
    handler = build_handler(raise_error=httpx2.ConnectError("connection refused"))
    generator, client = make_generator(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationUnavailableError):
            await generator.generate("hello", TEMPLATE, model=MODEL)


async def test_generator_cannot_read_a_response_with_non_json_content() -> None:
    """A 200 whose content isn't valid JSON fails as CardGenerationError, not silently."""
    # Arrange
    handler = build_handler(body=chat_completion_body(content="not json"))
    generator, client = make_generator(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationError):
            await generator.generate("hello", TEMPLATE, model=MODEL)


async def test_generator_cannot_read_a_refusal(caplog: pytest.LogCaptureFixture) -> None:
    """A model refusal is a distinct branch, not a confusing JSON parse failure on None content."""
    # Arrange
    handler = build_handler(body=chat_completion_body(content=None, refusal="cannot help with that"))
    generator, client = make_generator(handler)

    # Act
    async with client:
        with caplog.at_level(logging.WARNING), pytest.raises(CardGenerationError, match="cannot help with that"):
            await generator.generate("hello", TEMPLATE, model=MODEL)

    # Assert
    assert "cannot help with that" in caplog.text


async def test_generator_cannot_read_a_truncated_answer() -> None:
    """finish_reason == 'length' means truncated JSON, mapped explicitly rather than failing to parse."""
    # Arrange
    handler = build_handler(body=chat_completion_body(content='{"Word": "hel', finish_reason="length"))
    generator, client = make_generator(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationError):
            await generator.generate("hello", TEMPLATE, model=MODEL)


async def test_generator_cannot_leak_the_api_key_into_the_logs(caplog: pytest.LogCaptureFixture) -> None:
    """The OpenAI API key never reaches the log stream, even at DEBUG level."""
    # Arrange
    handler = build_handler()
    generator, client = make_generator(handler)

    # Act
    async with client:
        with caplog.at_level(logging.DEBUG):
            await generator.generate("hello", TEMPLATE, model=MODEL)

    # Assert
    assert FAKE_API_KEY not in caplog.text


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (ModelOption(id="gpt-5.6-luna", label="Luna", reasoning_effort="none"), "none"),
        (ModelOption(id="gpt-4.1", label="4.1"), None),
    ],
    ids=["pinned", "omitted"],
)
async def test_generator_can_pin_the_models_reasoning_effort(model: ModelOption, expected: str | None) -> None:
    """The catalog's reasoning effort reaches the request, and a model without one gets no such key at all."""
    # Arrange
    requests: list[httpx2.Request] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json=chat_completion_body(content='{"Word": "hello"}'))

    generator, client = make_generator(handler)

    # Act
    async with client:
        await generator.generate("hello", TEMPLATE, model=model)

    # Assert
    sent = json.loads(requests[0].content)
    assert sent["model"] == model.id
    assert sent.get("reasoning_effort") == expected
