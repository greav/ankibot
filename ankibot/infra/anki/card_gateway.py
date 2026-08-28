import logging
from dataclasses import dataclass
from typing import override

import httpx
from google.protobuf.message import Message

from ankibot.application.exceptions.anki import AnkiCardCreationError, AnkiSessionExpiredError
from ankibot.application.manage_cards.create_card import AddTarget, CardGateway, CreateCardRequest
from ankibot.infra.anki.protobuf import PROTOBUF_CONTENT_TYPE, parse_or_raise
from ankiweb.editor.add_or_update_pb2 import AddOrUpdateRequest, AddOrUpdateResponse
from ankiweb.editor.get_info_for_adding_pb2 import GetInfoForAddingRequest, GetInfoForAddingResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AnkiWebCardGatewayConfig:
    ankiuser_base_url: str


class AnkiWebCardGateway(CardGateway):
    """Adds notes through AnkiWeb's editor endpoints.

    See docs/ankiweb-api.md for the `editor/get-info-for-adding` → `editor/add-or-update` chain.
    """

    def __init__(self, config: AnkiWebCardGatewayConfig, client: httpx.AsyncClient) -> None:
        self._config = config
        self._client = client

    @override
    async def current_add_target(self) -> AddTarget:
        response = await self._post("/svc/editor/get-info-for-adding", GetInfoForAddingRequest())
        info = parse_or_raise(
            GetInfoForAddingResponse(),
            response.content,
            AnkiCardCreationError("AnkiWeb get-info-for-adding returned a non-protobuf response"),
        )

        deck_name = next((deck.name for deck in info.decks if deck.id == info.current_deck_id), None)
        if deck_name is None:
            raise AnkiCardCreationError(f"AnkiWeb's current_deck_id {info.current_deck_id} matches no known deck")

        return AddTarget(
            deck_id=info.current_deck_id,
            notetype_id=info.current_notetype_id,
            deck_name=deck_name,
            field_count=len(info.fields),
        )

    @override
    async def add_card(self, target: AddTarget, request: CreateCardRequest) -> None:
        add_request = AddOrUpdateRequest(
            fields=[request.front, request.back],
            tags="",
            add=AddOrUpdateRequest.AddMode(notetype_id=target.notetype_id, deck_id=target.deck_id),
        )
        response = await self._post("/svc/editor/add-or-update", add_request)
        parse_or_raise(
            AddOrUpdateResponse(),
            response.content,
            AnkiCardCreationError("AnkiWeb add-or-update returned a non-protobuf response"),
        )

        logger.info("Added card to AnkiWeb", extra={"deck_id": target.deck_id})

    async def _post(self, path: str, request: Message) -> httpx.Response:
        try:
            response = await self._client.post(
                f"{self._config.ankiuser_base_url}{path}",
                content=request.SerializeToString(),
                headers={"Content-Type": PROTOBUF_CONTENT_TYPE},
            )
        except httpx.HTTPError as error:
            raise AnkiCardCreationError(f"Failed to reach AnkiWeb {path}") from error

        if response.status_code == httpx.codes.FORBIDDEN:
            raise AnkiSessionExpiredError
        if response.status_code != httpx.codes.OK:
            raise AnkiCardCreationError(f"AnkiWeb {path} returned HTTP {response.status_code}")

        return response
