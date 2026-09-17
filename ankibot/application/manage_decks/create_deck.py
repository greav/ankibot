import logging
from dataclasses import dataclass

from ankibot.application.common.selected_deck_store import SelectedDeckStore
from ankibot.application.exceptions.anki import AnkiDeckCreationError
from ankibot.application.exceptions.decks import BlankDeckNameError, DeckAlreadyExistsError
from ankibot.application.manage_decks.ports import Deck, DeckGateway

DECK_NAME_SEPARATOR = "::"


@dataclass(frozen=True, kw_only=True)
class CreateDeckRequest:
    user_id: int
    name: str


@dataclass(frozen=True, kw_only=True)
class CreateDeckResult:
    deck_name: str
    """The name as AnkiWeb lists it; the new deck is now the user's target for new cards."""


logger = logging.getLogger(__name__)


def normalize_deck_name(raw: str) -> str | None:
    """The deck name Anki would store for ``raw``, or None when nothing is left to name a deck with.

    Anki nests decks on ``::`` and trims each level, so ``" Spanish :: Verbs "`` names the deck
    ``Verbs`` under ``Spanish``. A blank level (``"Spanish::"``) names no deck at all: Anki would
    silently drop it, and a name the user did not type is worse than asking again.
    """
    levels = [level.strip() for level in raw.split(DECK_NAME_SEPARATOR)]
    if any(not level for level in levels):
        return None
    return DECK_NAME_SEPARATOR.join(levels)


def find_deck_named(decks: list[Deck], name: str) -> Deck | None:
    """The deck called ``name``, compared the way Anki does: unique ignoring case."""
    wanted = name.casefold()
    return next((deck for deck in decks if deck.name.casefold() == wanted), None)


class CreateDeck:
    def __init__(self, gateway: DeckGateway, selected_decks: SelectedDeckStore) -> None:
        self._gateway = gateway
        self._selected_decks = selected_decks

    async def execute(self, request: CreateDeckRequest) -> CreateDeckResult:
        name = normalize_deck_name(request.name)
        if name is None:
            raise BlankDeckNameError

        existing = find_deck_named(await self._gateway.list_decks(), name)
        if existing is not None:
            # AnkiWeb answers a duplicate with a silent no-op; without this check the user would be
            # told a deck was created when nothing changed.
            raise DeckAlreadyExistsError(existing.name)

        await self._gateway.create_deck(name)

        # create-deck returns no id, so the only way to learn the new deck's is to list again.
        created = find_deck_named(await self._gateway.list_decks(), name)
        if created is None:
            logger.warning("AnkiWeb accepted a new deck for user %s but does not list it", request.user_id)
            raise AnkiDeckCreationError("AnkiWeb accepted the deck but does not list it")

        await self._selected_decks.set_deck(request.user_id, created.id)
        return CreateDeckResult(deck_name=created.name)
