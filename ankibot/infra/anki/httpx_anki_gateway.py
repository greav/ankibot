from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from google.protobuf.message import Message

from ankibot.application.english_card_generation.models import AddNotePayload, EditorInfo
from ankibot.application.english_card_generation.protocols import AnkiWebGateway
from ankibot.application.exceptions.card_generation import AnkiAPIError, AuthenticationError
from ankibot.infra.proto import auth_pb2, decks_pb2, notes_pb2

logger = logging.getLogger(__name__)

PROTO_HEADERS = {
    "Content-Type": "application/x-protobuf",
    "Accept": "application/x-protobuf",
}


@dataclass(slots=True)
class AnkiWebGatewayConfig:
    username: str
    password: str
    api_base_url: str = "https://ankiweb.net"
    account_base_url: str = "https://ankiuser.net"
    request_timeout: float = 15.0


class HttpxAnkiWebGateway(AnkiWebGateway):
    def __init__(
        self,
        config: AnkiWebGatewayConfig,
        client: httpx.AsyncClient | None = None,
        account_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._client = client or httpx.AsyncClient(
            base_url=config.api_base_url,
            timeout=config.request_timeout,
            headers=PROTO_HEADERS,
            cookies=httpx.Cookies(),
        )
        self._account_client = account_client or httpx.AsyncClient(
            base_url=config.account_base_url,
            timeout=config.request_timeout,
            cookies=self._client.cookies,
        )
        self._authenticated = False

    async def get_default_deck_id(self) -> int:
        content = await self._post_proto(
            "/svc/decks/deck-list-info",
            decks_pb2.DecksInfo(),
        )

        response = decks_pb2.DecksInfoResponse()
        response.ParseFromString(content)

        if not response.current_deck_id:
            raise AnkiAPIError("Deck information response is missing current deck id")

        return response.current_deck_id

    async def get_editor_info(self) -> EditorInfo:
        content = await self._post_proto("/svc/editor/get-info-for-adding")
        response = notes_pb2.GetInfoResponse()
        response.ParseFromString(content)

        if not response.current_notetype_id:
            raise AnkiAPIError("Editor info response is missing notetype id")

        field_order = [field.name for field in response.fields]
        return EditorInfo(notetype_id=response.current_notetype_id, field_order=field_order)

    async def add_note(self, payload: AddNotePayload) -> int:
        request = notes_pb2.AddOrUpdateRequest()
        request.fields.extend(payload.fields)
        request.tags = " ".join(payload.tags)

        add_mode = notes_pb2.AddOrUpdateRequest.AddMode()
        add_mode.notetype_id = payload.notetype_id
        add_mode.deck_id = payload.deck_id
        request.add.CopyFrom(add_mode)

        content = await self._post_proto("/svc/editor/add-note", request)
        response = notes_pb2.AddOrUpdateResponse()
        response.ParseFromString(content)

        if not response.note_id:
            raise AnkiAPIError("Add note response does not contain note id")

        return response.note_id

    async def _post_proto(self, endpoint: str, payload: Message | None = None) -> bytes:
        await self._ensure_authenticated()
        content = payload.SerializeToString() if payload is not None else b""

        response = await self._client.post(endpoint, content=content)
        response.raise_for_status()
        return response.content

    async def _ensure_authenticated(self) -> None:
        if self._authenticated:
            return

        logger.info("Authenticating with AnkiWeb")
        auth_request = auth_pb2.Auth(username=self._config.username, password=self._config.password)
        response = await self._client.post("/svc/account/login", content=auth_request.SerializeToString())
        response.raise_for_status()

        auth_response = auth_pb2.AuthResponse()
        auth_response.ParseFromString(response.content)

        if auth_response.status != auth_pb2.AuthResponse.AUTHENTICATED:
            raise AuthenticationError("Invalid AnkiWeb credentials")

        account_response = await self._account_client.get(
            "/account/ankiuser-login",
            params={"t": auth_response.token},
        )
        account_response.raise_for_status()

        self._authenticated = True

    async def aclose(self) -> None:
        await self._client.aclose()
        await self._account_client.aclose()

    async def __aenter__(self) -> HttpxAnkiWebGateway:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()
