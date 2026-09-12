from dataclasses import dataclass

from ankibot.application.common.selected_deck_store import SelectedDeckStore
from ankibot.application.manage_decks.ports import Deck, DeckGateway


@dataclass(frozen=True, kw_only=True)
class ListDecksRequest:
    user_id: int


@dataclass(frozen=True, kw_only=True)
class ListDecksResult:
    decks: list[Deck]
    selected_deck_id: int | None


class ListDecks:
    def __init__(self, gateway: DeckGateway, selected_decks: SelectedDeckStore) -> None:
        self._gateway = gateway
        self._selected_decks = selected_decks

    async def execute(self, request: ListDecksRequest) -> ListDecksResult:
        decks = await self._gateway.list_decks()
        selected_deck_id = await self._selected_decks.get_deck(request.user_id)
        return ListDecksResult(decks=decks, selected_deck_id=selected_deck_id)
