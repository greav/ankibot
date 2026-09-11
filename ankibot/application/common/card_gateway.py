"""The plain front/back card gateway, shared by every use case that writes such cards to AnkiWeb."""

import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

from ankibot.application.exceptions.anki import AnkiUnsupportedNotetypeError

# A plain front/back note carries exactly two fields — AnkiWeb rejects add-or-update outright
# when the number of fields sent doesn't match the target notetype's, so a notetype with any other
# field count can't take a front/back note.
FRONT_BACK_FIELD_COUNT = 2


@dataclass(frozen=True, kw_only=True)
class AddTarget:
    """Where AnkiWeb would currently add a note — whatever the editor reports as current."""

    deck_id: int
    notetype_id: int
    deck_name: str
    field_count: int


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
    async def add_card(self, target: AddTarget, front: str, back: str) -> None:
        """Add a note to ``target``, or raise ``AnkiSessionExpiredError``/``AnkiCardCreationError``."""
        raise NotImplementedError


logger = logging.getLogger(__name__)


def ensure_front_back(target: AddTarget) -> None:
    """Raise ``AnkiUnsupportedNotetypeError`` unless ``target`` takes a plain front/back note."""
    if target.field_count != FRONT_BACK_FIELD_COUNT:
        logger.warning("AnkiWeb's current notetype %s is not front/back", target.notetype_id)
        raise AnkiUnsupportedNotetypeError
