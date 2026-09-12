import json
import logging
from typing import Any

import httpx2
import pytest
from openai import AsyncOpenAI

from ankibot.application.common.dto.image import Image
from ankibot.application.common.model_catalog import ModelOption
from ankibot.application.exceptions.generation import CardGenerationError, CardGenerationUnavailableError
from ankibot.infra.llm.vocabulary_card.openai_word_suggester import OpenAIWordSuggester, OpenAIWordSuggesterConfig
from tests.common.transport import OpenAIHandler, openai_client_for

FAKE_API_KEY = "sk-test-distinctive-s3cr3t-not-real"
MODEL = ModelOption(id="gpt-4o-mini", label="GPT-4o mini")
SCREENSHOT = Image(data=b"fake-jpeg", mime_type="image/jpeg")


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


def words_content(*words: str) -> str:
    return json.dumps({"words": list(words)})


def build_handler(
    *, status_code: int = 200, body: dict[str, Any] | None = None, raise_error: Exception | None = None
) -> OpenAIHandler:
    async def handler(request: httpx2.Request) -> httpx2.Response:
        if raise_error is not None:
            raise raise_error
        assert request.url.path == "/v1/chat/completions"
        payload = body if body is not None else chat_completion_body(content=words_content("serendipity"))
        return httpx2.Response(status_code, json=payload)

    return handler


def make_suggester(
    handler: OpenAIHandler, *, max_candidates: int = 6
) -> tuple[OpenAIWordSuggester, httpx2.AsyncClient]:
    client = openai_client_for(handler)
    openai_client = AsyncOpenAI(api_key=FAKE_API_KEY, http_client=client, max_retries=0)
    config = OpenAIWordSuggesterConfig(max_candidates=max_candidates)
    return OpenAIWordSuggester(config, openai_client), client


async def test_suggester_can_pick_words_off_a_screenshot_with_a_strict_schema() -> None:
    """The screenshot goes as an image part under a strict words schema, and the answer is cut to the cap."""
    # Arrange
    requests: list[httpx2.Request] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(
            200, json=chat_completion_body(content=words_content("serendipity", "ubiquitous", "gist"))
        )

    suggester, client = make_suggester(handler, max_candidates=2)

    # Act
    async with client:
        result = await suggester.suggest(SCREENSHOT, model=MODEL)

    # Assert
    assert result == ("serendipity", "ubiquitous")
    sent = json.loads(requests[0].content)
    assert sent["model"] == MODEL.id
    assert "at most 2" in sent["messages"][0]["content"]
    parts = sent["messages"][1]["content"]
    assert parts[0]["type"] == "image_url"
    assert parts[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    json_schema = sent["response_format"]["json_schema"]
    assert json_schema["strict"] is True
    assert list(json_schema["schema"]["properties"]) == ["words"]


async def test_suggester_cannot_pick_words_on_a_rate_limit() -> None:
    """A 429 from OpenAI surfaces as CardGenerationUnavailableError, not a raw SDK exception."""
    # Arrange
    handler = build_handler(status_code=429, body={"error": {"message": "rate limited", "type": "rate_limit"}})
    suggester, client = make_suggester(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationUnavailableError):
            await suggester.suggest(SCREENSHOT, model=MODEL)


async def test_suggester_cannot_read_a_refusal(caplog: pytest.LogCaptureFixture) -> None:
    """A model refusal is a distinct branch, not a confusing parse failure on None content."""
    # Arrange
    handler = build_handler(body=chat_completion_body(content=None, refusal="cannot help with that"))
    suggester, client = make_suggester(handler)

    # Act
    async with client:
        with caplog.at_level(logging.WARNING), pytest.raises(CardGenerationError, match="cannot help with that"):
            await suggester.suggest(SCREENSHOT, model=MODEL)

    # Assert
    assert "cannot help with that" in caplog.text


async def test_suggester_cannot_read_an_answer_of_the_wrong_shape() -> None:
    """Valid JSON that is not a word list fails as CardGenerationError, not silently."""
    # Arrange
    handler = build_handler(body=chat_completion_body(content=json.dumps({"candidates": ["x"]})))
    suggester, client = make_suggester(handler)

    # Act / Assert
    async with client:
        with pytest.raises(CardGenerationError):
            await suggester.suggest(SCREENSHOT, model=MODEL)


async def test_suggester_cannot_leak_the_api_key_into_the_logs(caplog: pytest.LogCaptureFixture) -> None:
    """The OpenAI API key never reaches the log stream, even at DEBUG level."""
    # Arrange
    suggester, client = make_suggester(build_handler())

    # Act
    async with client:
        with caplog.at_level(logging.DEBUG):
            await suggester.suggest(SCREENSHOT, model=MODEL)

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
async def test_suggester_can_pin_the_models_reasoning_effort(model: ModelOption, expected: str | None) -> None:
    """The catalog's reasoning effort reaches the request, and a model without one gets no such key at all."""
    # Arrange
    requests: list[httpx2.Request] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json=chat_completion_body(content=words_content("serendipity")))

    suggester, client = make_suggester(handler)

    # Act
    async with client:
        await suggester.suggest(SCREENSHOT, model=model)

    # Assert
    sent = json.loads(requests[0].content)
    assert sent["model"] == model.id
    assert sent.get("reasoning_effort") == expected
