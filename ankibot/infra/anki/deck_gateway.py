from typing import override

from ankibot.application.exceptions.anki import AnkiDeckListingError
from ankibot.application.manage_decks.ports import Deck, DeckGateway
from ankibot.infra.anki.svc import AnkiSvcClient
from ankiweb.editor.get_info_for_adding_pb2 import GetInfoForAddingRequest, GetInfoForAddingResponse


class AnkiWebDeckGateway(DeckGateway):
    """Reads the deck list out of AnkiWeb's editor endpoint.

    ``editor/get-info-for-adding`` already returns every deck, so listing them needs no separate
    endpoint. It lives on ankiuser.net, not ankiweb.net.
    """

    def __init__(self, svc: AnkiSvcClient) -> None:
        self._svc = svc

    @override
    async def list_decks(self) -> list[Deck]:
        info = await self._svc.post(
            "/svc/editor/get-info-for-adding",
            GetInfoForAddingRequest(),
            GetInfoForAddingResponse(),
            error=AnkiDeckListingError,
        )
        return [Deck(id=deck.id, name=deck.name) for deck in info.decks]
