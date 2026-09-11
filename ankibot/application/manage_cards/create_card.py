from dataclasses import dataclass

from ankibot.application.common.card_gateway import CardGateway, ensure_front_back
from ankibot.application.common.selected_deck_store import SelectedDeckStore, chosen_deck


@dataclass(frozen=True, kw_only=True)
class CreateCardRequest:
    user_id: int
    front: str
    back: str


@dataclass(frozen=True, kw_only=True)
class CreateCardResult:
    deck_name: str


class CreateCard:
    def __init__(self, gateway: CardGateway, selected_decks: SelectedDeckStore) -> None:
        self._gateway = gateway
        self._selected_decks = selected_decks

    async def execute(self, request: CreateCardRequest) -> CreateCardResult:
        deck_id = await chosen_deck(self._selected_decks, request.user_id)
        target = await self._gateway.add_target(deck_id)
        ensure_front_back(target)
        await self._gateway.add_card(target, request.front, request.back)
        return CreateCardResult(deck_name=target.deck_name)
