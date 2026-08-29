from dataclasses import dataclass

import httpx
from google.protobuf.message import Message

from ankibot.application.exceptions.anki import AnkiSessionExpiredError
from ankibot.application.exceptions.base import ApplicationError
from ankibot.infra.anki.protobuf import PROTOBUF_CONTENT_TYPE, parse_or_raise


@dataclass(frozen=True, kw_only=True)
class AnkiSvcClientConfig:
    ankiuser_base_url: str


class AnkiSvcClient:
    """POSTs a protobuf message to an AnkiWeb /svc endpoint and parses the protobuf reply.

    The encoding half of the AnkiWeb gateways: it mirrors the wire protocol and knows nothing about
    decks or cards. The gateways composed over it do the domain-shaped half, and each names the
    error its own callers expect — which is why ``error`` is a per-call argument and not a field.
    ``AnkiSessionExpiredError`` is the exception: a 403 means the same thing on every /svc endpoint.
    """

    def __init__(self, config: AnkiSvcClientConfig, client: httpx.AsyncClient) -> None:
        self._config = config
        self._client = client

    async def post[M: Message](
        self,
        path: str,
        request: Message,
        response: M,
        *,
        error: type[ApplicationError],
    ) -> M:
        """Send ``request`` to ``path`` and parse the reply into ``response``."""
        try:
            http_response = await self._client.post(
                f"{self._config.ankiuser_base_url}{path}",
                content=request.SerializeToString(),
                headers={"Content-Type": PROTOBUF_CONTENT_TYPE},
            )
        except httpx.HTTPError as transport_error:
            raise error(f"Failed to reach AnkiWeb {path}") from transport_error

        if http_response.status_code == httpx.codes.FORBIDDEN:
            raise AnkiSessionExpiredError
        if http_response.status_code != httpx.codes.OK:
            raise error(f"AnkiWeb {path} returned HTTP {http_response.status_code}")

        return parse_or_raise(
            response,
            http_response.content,
            error(f"AnkiWeb {path} returned a non-protobuf response"),
        )
