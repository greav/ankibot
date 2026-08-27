"""HTTP test doubles: an httpx client whose transport is a plain handler function, no network involved."""

from collections.abc import Callable, Coroutine
from typing import Any

import httpx

Handler = Callable[[httpx.Request], Coroutine[Any, Any, httpx.Response]]


def client_for(handler: Handler) -> httpx.AsyncClient:
    """Build an ``AsyncClient`` routing every request to ``handler`` instead of the network."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))
