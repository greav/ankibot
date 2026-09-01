"""The rule turning the raw config value into the allowlist, tested as the plain function it is."""

import pytest

from ankibot.presentation.middlewares.access import parse_allowed_user_ids


def test_owner_can_allow_a_single_user() -> None:
    """One id in the config admits exactly that user."""
    assert parse_allowed_user_ids("123456789") == {123456789}


def test_owner_can_allow_several_users() -> None:
    """A comma-separated list admits each listed user, whitespace around entries ignored."""
    assert parse_allowed_user_ids(" 111, 222 ,333 ") == {111, 222, 333}


def test_owner_cannot_start_the_bot_with_an_empty_allowlist() -> None:
    """A blank value would lock everyone out, so it must stop the bot at startup instead."""
    with pytest.raises(ValueError, match="allowlist is empty"):
        parse_allowed_user_ids("  ")


def test_owner_cannot_start_the_bot_with_a_malformed_allowlist() -> None:
    """An entry that is not an integer is a misconfiguration, not a user to silently skip."""
    with pytest.raises(ValueError):
        parse_allowed_user_ids("111,@my_username")
