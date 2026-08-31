"""The generator's answer shape, and its cleanup into draft cards."""

from pydantic import BaseModel

from ankibot.application.add_snippet_cards import DraftCard


class AnswerCard(BaseModel):
    front: str
    back: str


class CardsAnswer(BaseModel):
    """What ``chat.completions.parse`` asks the model for and validates its answer against.

    The SDK derives the strict JSON schema from this model — ``additionalProperties``, ``required``
    and all — so the answer's shape lives here once, for the request and the parsed response alike.
    """

    cards: list[AnswerCard]


def to_draft_cards(answer: CardsAnswer, *, max_cards: int) -> tuple[DraftCard, ...]:
    """Clean the validated answer into draft cards.

    Model noise is cleaned rather than failed on: values are stripped, a card with a blank side is
    dropped, and anything past ``max_cards`` is cut — the schema cannot carry the cap (strict mode
    does not reliably honor ``maxItems``), so it is enforced here.
    """
    cards = tuple(
        DraftCard(front=front, back=back)
        for card in answer.cards
        if (front := card.front.strip()) and (back := card.back.strip())
    )
    return cards[:max_cards]
