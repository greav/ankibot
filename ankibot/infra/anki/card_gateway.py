import logging
from dataclasses import dataclass
from typing import override

from ankibot.application.common.card_gateway import AddTarget, CardGateway
from ankibot.application.exceptions.anki import (
    AnkiCardCreationError,
    AnkiDeckNotFoundError,
    AnkiTemplateTargetNotFoundError,
)
from ankibot.infra.anki.field_html import to_field_html
from ankibot.infra.anki.svc import AnkiSvcClient
from ankiweb.editor.add_or_update_pb2 import AddOrUpdateRequest, AddOrUpdateResponse
from ankiweb.editor.get_info_for_adding_pb2 import GetInfoForAddingRequest, GetInfoForAddingResponse
from ankiweb.editor.get_notetype_fields_pb2 import GetNotetypeFieldsRequest, GetNotetypeFieldsResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AnkiWebCardGatewayConfig:
    notetype_name: str


class AnkiWebCardGateway(CardGateway):
    """Adds notes through AnkiWeb's editor endpoints, with a configured notetype.

    The notetype is resolved by name rather than taken from what the editor reports as current:
    adding a note makes its notetype current, so relying on that would let one flow's add (a
    vocabulary card, with its many-field notetype) silently break the next front/back add.

    See docs/ankiweb-api.md for the `editor/get-info-for-adding` → `editor/get-notetype-fields` →
    `editor/add-or-update` chain.
    """

    def __init__(self, config: AnkiWebCardGatewayConfig, svc: AnkiSvcClient) -> None:
        self._config = config
        self._svc = svc

    @override
    async def add_target(self, deck_id: int) -> AddTarget:
        info = await self._svc.post(
            "/svc/editor/get-info-for-adding",
            GetInfoForAddingRequest(),
            GetInfoForAddingResponse(),
            error=AnkiCardCreationError,
        )

        deck_name = next((deck.name for deck in info.decks if deck.id == deck_id), None)
        if deck_name is None:
            logger.warning("The selected deck %s no longer exists in AnkiWeb", deck_id)
            raise AnkiDeckNotFoundError

        notetype_id = next(
            (notetype.id for notetype in info.notetypes if notetype.name == self._config.notetype_name), None
        )
        if notetype_id is None:
            available = ", ".join(notetype.name for notetype in info.notetypes)
            logger.warning("The configured card notetype is missing from AnkiWeb: %s", self._config.notetype_name)
            raise AnkiTemplateTargetNotFoundError(
                f"Notetype '{self._config.notetype_name}' not found in AnkiWeb. Available notetypes: {available}"
            )

        fields_response = await self._svc.post(
            "/svc/editor/get-notetype-fields",
            GetNotetypeFieldsRequest(notetype_id=notetype_id),
            GetNotetypeFieldsResponse(),
            error=AnkiCardCreationError,
        )

        return AddTarget(
            deck_id=deck_id,
            notetype_id=notetype_id,
            deck_name=deck_name,
            field_count=len(fields_response.fields),
        )

    @override
    async def add_card(self, target: AddTarget, front: str, back: str) -> None:
        add_request = AddOrUpdateRequest(
            fields=[to_field_html(front), to_field_html(back)],
            tags="",
            add=AddOrUpdateRequest.AddMode(notetype_id=target.notetype_id, deck_id=target.deck_id),
        )
        await self._svc.post(
            "/svc/editor/add-or-update",
            add_request,
            AddOrUpdateResponse(),
            error=AnkiCardCreationError,
        )

        logger.info("Added card to AnkiWeb deck %s", target.deck_id)
