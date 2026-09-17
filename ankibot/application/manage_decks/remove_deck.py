import logging
from dataclasses import dataclass

from ankibot.application.common.selected_deck_store import SelectedDeckStore
from ankibot.application.exceptions.anki import AnkiDeckNotFoundError
from ankibot.application.manage_decks.ports import DeckGateway


@dataclass(frozen=True, kw_only=True)
class RemoveDeckRequest:
    user_id: int
    deck_id: int


@dataclass(frozen=True, kw_only=True)
class RemoveDeckResult:
    deck_name: str
    was_target: bool
    """True when the deleted deck was where this user's new cards went; they now have no target."""


logger = logging.getLogger(__name__)


class RemoveDeck:
    def __init__(self, gateway: DeckGateway, selected_decks: SelectedDeckStore) -> None:
        self._gateway = gateway
        self._selected_decks = selected_decks

    async def execute(self, request: RemoveDeckRequest) -> RemoveDeckResult:
        decks = await self._gateway.list_decks()

        # The same lookup SelectDeck does: only the id travels in callback_data, and a deck deleted
        # since the keyboard was rendered must be refused rather than reported as deleted again.
        deck_name = next((deck.name for deck in decks if deck.id == request.deck_id), None)
        if deck_name is None:
            logger.info("The deck %s picked for deletion no longer exists in AnkiWeb", request.deck_id)
            raise AnkiDeckNotFoundError

        await self._gateway.remove_deck(request.deck_id)

        # Only this user's choice can be reset: the account is shared, and another user who
        # targets the same deck learns about it when their next card is refused.
        was_target = await self._selected_decks.get_deck(request.user_id) == request.deck_id
        if was_target:
            await self._selected_decks.clear_deck(request.user_id)

        return RemoveDeckResult(deck_name=deck_name, was_target=was_target)
