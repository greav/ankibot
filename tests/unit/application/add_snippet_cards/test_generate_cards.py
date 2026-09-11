"""``merge_cards`` decides what a regenerated batch is made of; ``execute`` around it is covered
through the handler."""

from ankibot.application.add_snippet_cards import DraftCard
from ankibot.application.add_snippet_cards.generate_cards import merge_cards

KEPT = (DraftCard(front="What is the GIL?", back="A lock"),)


def test_merge_can_put_the_kept_cards_before_the_generated_ones() -> None:
    """A regenerated batch opens with what the learner kept, then adds the new cards in order."""
    # Act
    result = merge_cards(KEPT, [DraftCard(front="Q2", back="A2"), DraftCard(front="Q3", back="A3")])

    # Assert
    assert result == (KEPT[0], DraftCard(front="Q2", back="A2"), DraftCard(front="Q3", back="A3"))


def test_merge_cannot_repeat_a_kept_card_the_generator_produced_again() -> None:
    """A generated card identical to a kept one is dropped rather than shown twice."""
    # Act
    result = merge_cards(KEPT, [KEPT[0], DraftCard(front="Q2", back="A2")])

    # Assert
    assert result == (KEPT[0], DraftCard(front="Q2", back="A2"))


def test_merge_can_keep_the_kept_cards_when_the_generator_finds_nothing_more() -> None:
    """A passage with nothing else worth a card still yields the kept cards, never an empty batch."""
    # Act / Assert
    assert merge_cards(KEPT, []) == KEPT
