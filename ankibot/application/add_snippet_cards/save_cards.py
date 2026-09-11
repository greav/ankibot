import logging
from dataclasses import dataclass

from ankibot.application.add_snippet_cards.generate_cards import DraftCard
from ankibot.application.common.card_gateway import CardGateway, ensure_front_back
from ankibot.application.common.selected_deck_store import SelectedDeckStore, chosen_deck
from ankibot.application.exceptions.anki import SnippetCardsPartiallySavedError
from ankibot.application.exceptions.base import ApplicationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SaveSnippetCardsRequest:
    user_id: int
    cards: tuple[DraftCard, ...]


@dataclass(frozen=True, kw_only=True)
class SaveSnippetCardsResult:
    deck_name: str
    saved: int


class SaveCards:
    def __init__(self, gateway: CardGateway, selected_decks: SelectedDeckStore) -> None:
        self._gateway = gateway
        self._selected_decks = selected_decks

    async def execute(self, request: SaveSnippetCardsRequest) -> SaveSnippetCardsResult:
        # Re-resolved rather than carried over from generation: the deck or notetype may have
        # changed while the preview sat unconfirmed.
        deck_id = await chosen_deck(self._selected_decks, request.user_id)
        target = await self._gateway.add_target(deck_id)
        ensure_front_back(target)

        # AnkiWeb adds one note per call; a batch that fails partway is reported as partial once
        # anything is in, and as the causing error itself when nothing is.
        saved = 0
        for card in request.cards:
            try:
                await self._gateway.add_card(target, card.front, card.back)
            except ApplicationError as error:
                if saved == 0:
                    raise
                logger.warning(
                    "Saved %d of %d snippet cards before AnkiWeb failed: %s", saved, len(request.cards), error
                )
                raise SnippetCardsPartiallySavedError(
                    saved=saved, total=len(request.cards), deck_name=target.deck_name
                ) from error
            saved += 1

        return SaveSnippetCardsResult(deck_name=target.deck_name, saved=saved)
