import logging
from typing import override

from ankibot.application.common.card_gateway import AddTarget, CardGateway
from ankibot.application.exceptions.anki import AnkiCardCreationError, AnkiDeckNotFoundError
from ankibot.infra.anki.svc import AnkiSvcClient
from ankiweb.editor.add_or_update_pb2 import AddOrUpdateRequest, AddOrUpdateResponse
from ankiweb.editor.get_info_for_adding_pb2 import GetInfoForAddingRequest, GetInfoForAddingResponse

logger = logging.getLogger(__name__)


class AnkiWebCardGateway(CardGateway):
    """Adds notes through AnkiWeb's editor endpoints.

    See docs/ankiweb-api.md for the `editor/get-info-for-adding` → `editor/add-or-update` chain.
    """

    def __init__(self, svc: AnkiSvcClient) -> None:
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

        return AddTarget(
            deck_id=deck_id,
            notetype_id=info.current_notetype_id,
            deck_name=deck_name,
            field_count=len(info.fields),
        )

    @override
    async def add_card(self, target: AddTarget, front: str, back: str) -> None:
        add_request = AddOrUpdateRequest(
            fields=[front, back],
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
