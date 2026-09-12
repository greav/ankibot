"""``resolve_model`` decides which model a user's card is written by; ``chosen_model`` around it is
covered through the handlers."""

from ankibot.application.common.model_catalog import ModelOption
from ankibot.application.common.selected_model_store import resolve_model

CHEAP = ModelOption(id="gpt-5.6-luna", label="Luna", reasoning_effort="none")
GOOD = ModelOption(id="gpt-5.6-terra", label="Terra", reasoning_effort="none")
OFFERED = (CHEAP, GOOD)


def test_user_can_have_their_stored_choice_honored() -> None:
    """A stored id still in the catalog resolves to that entry, reasoning effort and all."""
    # Act / Assert
    assert resolve_model("gpt-5.6-luna", OFFERED, GOOD) == CHEAP


def test_user_can_fall_back_to_the_default_without_a_choice() -> None:
    """Nobody has to open /model before their first card: no choice means the default."""
    # Act / Assert
    assert resolve_model(None, OFFERED, GOOD) == GOOD


def test_user_can_fall_back_to_the_default_when_their_choice_is_retired() -> None:
    """A stored id the operator dropped from the catalog no longer reaches the provider."""
    # Act / Assert
    assert resolve_model("gpt-3.5-turbo", OFFERED, GOOD) == GOOD
