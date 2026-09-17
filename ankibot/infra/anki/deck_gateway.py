from typing import override

from ankibot.application.exceptions.anki import AnkiDeckCreationError, AnkiDeckListingError, AnkiDeckRemovalError
from ankibot.application.manage_decks.ports import Deck, DeckGateway
from ankibot.infra.anki.svc import AnkiHost, AnkiSvcClient
from ankiweb.decks.create_deck_pb2 import CreateDeckRequest, CreateDeckResponse
from ankiweb.decks.remove_deck_pb2 import RemoveDeckRequest, RemoveDeckResponse
from ankiweb.editor.get_info_for_adding_pb2 import GetInfoForAddingRequest, GetInfoForAddingResponse


class AnkiWebDeckGateway(DeckGateway):
    """Reads the deck list out of AnkiWeb's editor endpoint and edits decks through its decks service.

    ``editor/get-info-for-adding`` already returns every deck, so listing them needs no separate
    endpoint. It lives on ankiuser.net; the ``decks/*`` endpoints that create and delete live on
    ankiweb.net, the other half of AnkiWeb's two-origin split.
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

    @override
    async def create_deck(self, name: str) -> None:
        await self._svc.post(
            "/svc/decks/create-deck",
            CreateDeckRequest(name=name),
            CreateDeckResponse(),
            error=AnkiDeckCreationError,
            host=AnkiHost.ANKIWEB,
        )

    @override
    async def remove_deck(self, deck_id: int) -> None:
        await self._svc.post(
            "/svc/decks/remove-deck",
            RemoveDeckRequest(deck_id=deck_id),
            RemoveDeckResponse(),
            error=AnkiDeckRemovalError,
            host=AnkiHost.ANKIWEB,
        )
