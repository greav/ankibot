"""HTTP test doubles: an httpx client whose transport is a plain handler function, no network involved."""

from collections.abc import Callable, Coroutine
from typing import Any

import httpx
import httpx2

Handler = Callable[[httpx.Request], Coroutine[Any, Any, httpx.Response]]
OpenAIHandler = Callable[[httpx2.Request], Coroutine[Any, Any, httpx2.Response]]


def client_for(handler: Handler) -> httpx.AsyncClient:
    """Build an ``AsyncClient`` routing every request to ``handler`` instead of the network."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def openai_client_for(handler: OpenAIHandler) -> httpx2.AsyncClient:
    """Build the ``httpx2.AsyncClient`` the ``openai`` SDK's ``http_client`` expects.

    The SDK depends on ``httpx2`` (a separate major-version package from the ``httpx`` the rest of
    the codebase uses), so ``AsyncOpenAI(http_client=...)`` cannot take a plain ``client_for`` client.
    """
    return httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
