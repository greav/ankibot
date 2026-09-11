import logging
from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ankibot.application.common.card_gateway import CardGateway, ensure_front_back
from ankibot.application.common.dto.image import Image
from ankibot.application.common.selected_deck_store import SelectedDeckStore, chosen_deck
from ankibot.application.exceptions.generation import CardGenerationEmptyError, CardGenerationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class Snippet:
    """One passage from the learner's reading: text or a screenshot, never both.

    ``hint`` is the learner's steer on what to focus on (a photo caption, typically).
    """

    text: str | None = None
    image: Image | None = None
    hint: str | None = None

    def __post_init__(self) -> None:
        if (self.text is None) == (self.image is None):
            msg = "A snippet carries exactly one of text or image"
            raise ValueError(msg)


@dataclass(frozen=True, kw_only=True)
class DraftCard:
    """One front/back card the learner is asked to confirm."""

    front: str
    back: str


class SnippetCardsGenerator(Protocol):
    """Distills a passage into front/back flashcards."""

    @abstractmethod
    async def generate(
        self, snippet: Snippet, *, kept: Sequence[DraftCard] = (), feedback: str | None = None
    ) -> Sequence[DraftCard]:
        """Return the cards worth keeping from ``snippet``, possibly none.

        ``kept`` are cards the learner has already accepted from this same passage: the answer
        covers other facts and leaves room for them under the generator's own cap. ``feedback``
        is the learner's note on what to change about the cards being replaced.

        Raises ``CardGenerationUnavailableError`` when the backend cannot be reached, and
        ``CardGenerationError`` when its answer cannot be read.
        """
        raise NotImplementedError


def blank_sided(cards: Sequence[DraftCard]) -> tuple[int, ...]:
    """Indices of cards a learner could not study — a side absent or blank after stripping."""
    return tuple(index for index, card in enumerate(cards) if not card.front.strip() or not card.back.strip())


def merge_cards(kept: Sequence[DraftCard], generated: Sequence[DraftCard]) -> tuple[DraftCard, ...]:
    """The kept cards first, then the generated ones that do not repeat a kept card verbatim."""
    return (*kept, *(card for card in generated if card not in kept))


@dataclass(frozen=True, kw_only=True)
class GenerateSnippetCardsRequest:
    """A regeneration carries ``kept``, what the learner accepted from the previous batch, and
    optionally ``feedback``, their note on what to change about the rest."""

    user_id: int
    snippet: Snippet
    kept: tuple[DraftCard, ...] = ()
    feedback: str | None = None


@dataclass(frozen=True, kw_only=True)
class GeneratedSnippetCards:
    """The cards the user is asked to confirm, and the deck they would land in."""

    deck_name: str
    cards: tuple[DraftCard, ...]


class GenerateCards:
    def __init__(
        self, gateway: CardGateway, selected_decks: SelectedDeckStore, generator: SnippetCardsGenerator
    ) -> None:
        self._gateway = gateway
        self._selected_decks = selected_decks
        self._generator = generator

    async def execute(self, request: GenerateSnippetCardsRequest) -> GeneratedSnippetCards:
        # The target is checked before the generator runs, so a wrong deck or notetype costs
        # nothing at the LLM.
        deck_id = await chosen_deck(self._selected_decks, request.user_id)
        target = await self._gateway.add_target(deck_id)
        ensure_front_back(target)

        generated = await self._generator.generate(request.snippet, kept=request.kept, feedback=request.feedback)
        if blanks := blank_sided(generated):
            logger.warning("Snippet cards left one-sided: %s", ", ".join(map(str, blanks)))
            raise CardGenerationError(f"The generator left card(s) {', '.join(map(str, blanks))} one-sided")

        # A kept card is never lost: when the generator finds nothing more, the batch is the kept
        # cards alone, and only a batch with nothing in it at all is empty.
        cards = merge_cards(request.kept, generated)
        if not cards:
            logger.info("The snippet held nothing card-worthy")
            raise CardGenerationEmptyError

        return GeneratedSnippetCards(deck_name=target.deck_name, cards=cards)
