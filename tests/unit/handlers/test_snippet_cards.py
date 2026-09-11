from ankibot.application.add_snippet_cards import DraftCard
from ankibot.application.exceptions.anki import SnippetCardsPartiallySavedError
from ankibot.presentation.handlers.snippet_cards import (
    TELEGRAM_MESSAGE_LIMIT,
    format_cards_preview,
    format_partial_save,
    format_saved,
    kept_cards,
)

STORED = [{"front": "Q1", "back": "A1"}, {"front": "Q2", "back": "A2"}]


def test_kept_cards_can_carry_the_ticked_cards_over() -> None:
    """Regenerate keeps exactly the ticked cards, as draft cards, in preview order."""
    # Act / Assert
    assert kept_cards(STORED, [False, True]) == (DraftCard(front="Q2", back="A2"),)


def test_kept_cards_cannot_keep_anything_when_nothing_is_unticked() -> None:
    """With every card ticked there is nothing to replace, so Regenerate starts the batch over."""
    # Act / Assert
    assert kept_cards(STORED, [True, True]) == ()


def test_format_cards_preview_can_render_every_card_in_order() -> None:
    """The preview names the deck, counts the cards and lists each front/back pair in order."""
    # Arrange
    cards = [
        DraftCard(front="What does GIL stand for?", back="Global Interpreter Lock"),
        DraftCard(front="Which lock serializes Python bytecode execution?", back="The GIL"),
    ]

    # Act
    result = format_cards_preview("Python", cards)

    # Assert
    assert result == [
        "Add 2 cards to Python?\n\n"
        "1. What does GIL stand for?\n— Global Interpreter Lock\n\n"
        "2. Which lock serializes Python bytecode execution?\n— The GIL"
    ]


def test_format_cards_preview_can_count_a_single_card_in_the_singular() -> None:
    """One card is offered as '1 card', not '1 cards'."""
    # Act
    result = format_cards_preview("Python", [DraftCard(front="Q", back="A")])

    # Assert
    assert result == ["Add 1 card to Python?\n\n1. Q\n— A"]


def test_format_cards_preview_cannot_exceed_telegram_message_limit() -> None:
    """A batch too long for one message splits into several, each within the limit, losing no card."""
    # Arrange
    cards = [DraftCard(front=f"Question {index} " + "q" * 700, back="a" * 700) for index in range(8)]

    # Act
    result = format_cards_preview("Python", cards)

    # Assert
    assert len(result) > 1
    assert all(len(message) <= TELEGRAM_MESSAGE_LIMIT for message in result)
    joined = "\n\n".join(result)
    for index in range(8):
        assert f"Question {index} " in joined


def test_format_saved_can_name_the_deck_and_count() -> None:
    """The save confirmation states how many cards landed where, singular and plural alike."""
    # Act / Assert
    assert format_saved(1, "Python") == "Added 1 card to Python."
    assert format_saved(3, "Python") == "Added 3 cards to Python."


def test_format_partial_save_can_state_what_made_it_in() -> None:
    """The partial-save reply names the saved count, the total and the deck, and asks to resend."""
    # Arrange
    error = SnippetCardsPartiallySavedError(saved=2, total=5, deck_name="Python")

    # Act
    result = format_partial_save(error)

    # Assert
    assert result == ("Saved 2 of 5 cards to Python, then AnkiWeb failed. Resend the snippet to add the rest.")
