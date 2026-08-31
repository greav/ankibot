from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ankibot.application.common.card_gateway import CardGateway, ensure_front_back
from ankibot.application.common.selected_deck_store import SelectedDeckStore
from ankibot.application.exceptions.generation import CardGenerationEmptyError, CardGenerationError


@dataclass(frozen=True, kw_only=True)
class SnippetImage:
    """A screenshot of the passage, as the bytes the generator will read."""

    data: bytes
    mime_type: str


@dataclass(frozen=True, kw_only=True)
class Snippet:
    """One passage from the learner's reading: text or a screenshot, never both.

    ``hint`` is the learner's steer on what to focus on (a photo caption, typically).
    """

    text: str | None = None
    image: SnippetImage | None = None
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
    async def generate(self, snippet: Snippet) -> Sequence[DraftCard]:
        """Return the cards worth keeping from ``snippet``, possibly none.

        Raises ``CardGenerationUnavailableError`` when the backend cannot be reached, and
        ``CardGenerationError`` when its answer cannot be read.
        """
        raise NotImplementedError


def blank_sided(cards: Sequence[DraftCard]) -> tuple[int, ...]:
    """Indices of cards a learner could not study — a side absent or blank after stripping."""
    return tuple(index for index, card in enumerate(cards) if not card.front.strip() or not card.back.strip())


@dataclass(frozen=True, kw_only=True)
class GenerateSnippetCardsRequest:
    user_id: int
    snippet: Snippet


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
        deck_id = await self._selected_decks.get(request.user_id)
        target = await self._gateway.add_target(deck_id)
        ensure_front_back(target)

        cards = await self._generator.generate(request.snippet)
        if not cards:
            raise CardGenerationEmptyError
        if blanks := blank_sided(cards):
            raise CardGenerationError(f"The generator left card(s) {', '.join(map(str, blanks))} one-sided")

        return GeneratedSnippetCards(deck_name=target.deck_name, cards=tuple(cards))
