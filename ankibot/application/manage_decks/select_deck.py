from dataclasses import dataclass

from ankibot.application.common.selected_deck_store import SelectedDeckStore
from ankibot.application.exceptions.anki import AnkiDeckNotFoundError
from ankibot.application.manage_decks.ports import DeckGateway


@dataclass(frozen=True, kw_only=True)
class SelectDeckRequest:
    user_id: int
    deck_id: int


@dataclass(frozen=True, kw_only=True)
class SelectDeckResult:
    deck_name: str


class SelectDeck:
    def __init__(self, gateway: DeckGateway, selected_decks: SelectedDeckStore) -> None:
        self._gateway = gateway
        self._selected_decks = selected_decks

    async def execute(self, request: SelectDeckRequest) -> SelectDeckResult:
        decks = await self._gateway.list_decks()

        # Resolving the id against AnkiWeb here is what keeps deck names out of Telegram's
        # 64-byte callback_data, and rejects a deck deleted since the keyboard was rendered.
        deck_name = next((deck.name for deck in decks if deck.id == request.deck_id), None)
        if deck_name is None:
            raise AnkiDeckNotFoundError

        await self._selected_decks.set(request.user_id, request.deck_id)
        return SelectDeckResult(deck_name=deck_name)
