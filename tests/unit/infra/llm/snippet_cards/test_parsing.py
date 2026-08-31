from ankibot.application.add_snippet_cards import DraftCard
from ankibot.infra.llm.snippet_cards.parsing import AnswerCard, CardsAnswer, to_draft_cards


def test_to_draft_cards_can_clean_a_card_list() -> None:
    """A validated answer becomes draft cards with stripped values, in the model's order."""
    # Arrange
    answer = CardsAnswer(cards=[AnswerCard(front=" Q1 ", back="A1"), AnswerCard(front="Q2", back=" A2 ")])

    # Act
    result = to_draft_cards(answer, max_cards=8)

    # Assert
    assert result == (DraftCard(front="Q1", back="A1"), DraftCard(front="Q2", back="A2"))


def test_to_draft_cards_can_drop_a_card_with_a_blank_side() -> None:
    """A card the model left one-sided is dropped rather than shown or failed on."""
    # Arrange
    answer = CardsAnswer(cards=[AnswerCard(front="Q1", back="   "), AnswerCard(front="Q2", back="A2")])

    # Act
    result = to_draft_cards(answer, max_cards=8)

    # Assert
    assert result == (DraftCard(front="Q2", back="A2"),)


def test_to_draft_cards_cannot_exceed_the_configured_cap() -> None:
    """The cap is enforced here because the strict schema cannot carry it: extra cards are cut."""
    # Arrange
    answer = CardsAnswer(cards=[AnswerCard(front=f"Q{index}", back=f"A{index}") for index in range(10)])

    # Act
    result = to_draft_cards(answer, max_cards=3)

    # Assert
    assert len(result) == 3
    assert result[0] == DraftCard(front="Q0", back="A0")
