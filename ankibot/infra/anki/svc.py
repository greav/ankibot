import logging
from dataclasses import dataclass
from enum import StrEnum

import httpx
from google.protobuf.message import Message

from ankibot.application.exceptions.anki import AnkiSessionExpiredError
from ankibot.application.exceptions.base import ApplicationError
from ankibot.infra.anki.protobuf import PROTOBUF_CONTENT_TYPE, parse_or_raise


@dataclass(frozen=True, kw_only=True)
class AnkiSvcClientConfig:
    ankiweb_base_url: str
    ankiuser_base_url: str


class AnkiHost(StrEnum):
    """The two origins AnkiWeb splits its /svc endpoints across; each has its own session cookie.

    Account, deck management and the shared catalog live on ankiweb.net; study and note editing
    live on ankiuser.net. The split is a security boundary (card HTML runs on ankiuser.net), so a
    call sent to the wrong host is refused, not redirected.
    """

    ANKIWEB = "ankiweb"
    ANKIUSER = "ankiuser"


logger = logging.getLogger(__name__)


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
        host: AnkiHost = AnkiHost.ANKIUSER,
    ) -> M:
        """Send ``request`` to ``path`` on ``host`` and parse the reply into ``response``.

        ``host`` defaults to ankiuser.net because that is where the editor endpoints every card
        gateway calls live; the deck-management gateway names ankiweb.net explicitly.
        """
        try:
            return await self._post(path, request, response, error=error, host=host)
        except AnkiSessionExpiredError:
            logger.info("AnkiWeb session expired at %s", path)
            raise
        except ApplicationError as failure:
            logger.warning("AnkiWeb call failed: %s", failure)
            raise

    async def _post[M: Message](
        self,
        path: str,
        request: Message,
        response: M,
        *,
        error: type[ApplicationError],
        host: AnkiHost,
    ) -> M:
        try:
            http_response = await self._client.post(
                f"{self._base_url(host)}{path}",
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

    def _base_url(self, host: AnkiHost) -> str:
        if host is AnkiHost.ANKIWEB:
            return self._config.ankiweb_base_url
        return self._config.ankiuser_base_url
