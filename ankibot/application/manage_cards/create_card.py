from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

from ankibot.application.common.selected_deck_store import SelectedDeckStore
from ankibot.application.exceptions.anki import AnkiUnsupportedNotetypeError

# CreateCardRequest carries exactly a front and a back — AnkiWeb rejects add-or-update outright
# when the number of fields sent doesn't match the target notetype's, so a notetype with any other
# field count can't take a plain front/back note.
FRONT_BACK_FIELD_COUNT = 2


@dataclass(frozen=True, kw_only=True)
class CreateCardRequest:
    user_id: int
    front: str
    back: str


@dataclass(frozen=True, kw_only=True)
class AddTarget:
    """Where AnkiWeb would currently add a note — whatever the editor reports as current."""

    deck_id: int
    notetype_id: int
    deck_name: str
    field_count: int


@dataclass(frozen=True, kw_only=True)
class CreateCardResult:
    deck_name: str


class CardGateway(Protocol):
    """Adds a note to a deck of the AnkiWeb account, with the current notetype."""

    @abstractmethod
    async def add_target(self, deck_id: int | None) -> AddTarget:
        """Return the target for ``deck_id``, or AnkiWeb's current deck when it is None.

        Raises ``AnkiDeckNotFoundError`` when the account no longer has ``deck_id``, and
        ``AnkiSessionExpiredError``/``AnkiCardCreationError`` as any other AnkiWeb read does.
        """
        raise NotImplementedError

    @abstractmethod
    async def add_card(self, target: AddTarget, request: CreateCardRequest) -> None:
        """Add a note to ``target``, or raise ``AnkiSessionExpiredError``/``AnkiCardCreationError``."""
        raise NotImplementedError


class CreateCard:
    def __init__(self, gateway: CardGateway, selected_decks: SelectedDeckStore) -> None:
        self._gateway = gateway
        self._selected_decks = selected_decks

    async def execute(self, request: CreateCardRequest) -> CreateCardResult:
        deck_id = await self._selected_decks.get(request.user_id)
        target = await self._gateway.add_target(deck_id)
        if target.field_count != FRONT_BACK_FIELD_COUNT:
            raise AnkiUnsupportedNotetypeError
        await self._gateway.add_card(target, request)
        return CreateCardResult(deck_name=target.deck_name)
