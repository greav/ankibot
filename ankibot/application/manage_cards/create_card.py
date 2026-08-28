from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

from ankibot.application.exceptions.anki import AnkiUnsupportedNotetypeError

# CreateCardRequest carries exactly a front and a back — AnkiWeb rejects add-or-update outright
# when the number of fields sent doesn't match the target notetype's, so a notetype with any other
# field count can't take a plain front/back note.
FRONT_BACK_FIELD_COUNT = 2


@dataclass(frozen=True, kw_only=True)
class CreateCardRequest:
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
    """Adds a note to AnkiWeb's current deck and notetype."""

    @abstractmethod
    async def current_add_target(self) -> AddTarget:
        """Return AnkiWeb's current deck/notetype, or raise ``AnkiSessionExpiredError``/``AnkiCardCreationError``."""
        raise NotImplementedError

    @abstractmethod
    async def add_card(self, target: AddTarget, request: CreateCardRequest) -> None:
        """Add a note to ``target``, or raise ``AnkiSessionExpiredError``/``AnkiCardCreationError``."""
        raise NotImplementedError


class CreateCard:
    def __init__(self, gateway: CardGateway) -> None:
        self._gateway = gateway

    async def execute(self, request: CreateCardRequest) -> CreateCardResult:
        target = await self._gateway.current_add_target()
        if target.field_count != FRONT_BACK_FIELD_COUNT:
            raise AnkiUnsupportedNotetypeError
        await self._gateway.add_card(target, request)
        return CreateCardResult(deck_name=target.deck_name)
