"""The JSON file behind every user's deck choice.

What matters is that a choice outlives the process, so every assertion that reads a choice back
goes through a fresh store over the same file: the dict inside one instance is not the guarantee,
the file is. It is shared mutable state as well, so it gets the concurrency test.
"""

import asyncio
from pathlib import Path

import pytest

from ankibot.infra.selected_decks import JsonFileSelectedDeckStore, JsonFileSelectedDeckStoreConfig


def make_store(path: Path) -> JsonFileSelectedDeckStore:
    """A store over ``path``, the way the bot would build one at start."""
    return JsonFileSelectedDeckStore(JsonFileSelectedDeckStoreConfig(path=str(path)))


async def test_user_cannot_see_a_deck_they_never_picked(tmp_path: Path) -> None:
    """With no file yet, an unknown user has no selection, so the bot asks them to choose one."""
    # Arrange
    store = make_store(tmp_path / "decks" / "selected_decks.json")

    # Act
    selected = await store.get(user_id=1)

    # Assert
    assert selected is None


async def test_user_can_keep_their_deck_across_a_restart(tmp_path: Path) -> None:
    """A deck picked before a restart is still the user's deck after it."""
    # Arrange
    path = tmp_path / "decks" / "selected_decks.json"
    await make_store(path).set(user_id=1, deck_id=10)

    # Act
    selected = await make_store(path).get(user_id=1)

    # Assert
    assert selected == 10


async def test_user_can_change_their_deck(tmp_path: Path) -> None:
    """Picking again replaces the earlier choice, and that is what survives the restart."""
    # Arrange
    path = tmp_path / "selected_decks.json"
    store = make_store(path)
    await store.set(user_id=1, deck_id=10)

    # Act
    await store.set(user_id=1, deck_id=20)

    # Assert
    assert await make_store(path).get(user_id=1) == 20


async def test_bot_cannot_start_over_a_corrupt_deck_file(tmp_path: Path) -> None:
    """A file that is not a map of ids refuses to load, so the bot stops at launch rather than misfile cards."""
    # Arrange
    path = tmp_path / "selected_decks.json"
    path.write_text('"not an object"')

    # Act / Assert
    with pytest.raises(ValueError, match=str(path)):
        make_store(path)


async def test_two_users_can_pick_different_decks_concurrently(tmp_path: Path) -> None:
    """Concurrent choices are keyed per user and both reach the file; neither overwrites the other's deck."""
    # Arrange
    path = tmp_path / "selected_decks.json"
    store = make_store(path)

    async def pick(user_id: int, deck_id: int) -> None:
        await store.set(user_id, deck_id)
        await asyncio.sleep(0)

    # Act
    await asyncio.gather(pick(1, 10), pick(2, 20))

    # Assert
    reloaded = make_store(path)
    assert (await reloaded.get(1), await reloaded.get(2)) == (10, 20)
