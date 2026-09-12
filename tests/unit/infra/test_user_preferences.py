"""The JSON file behind every user's deck and model choice.

What matters is that a choice outlives the process, so every assertion that reads a choice back
goes through a fresh store over the same file: the dict inside one instance is not the guarantee,
the file is. It is shared mutable state as well, so it gets the concurrency tests.
"""

import asyncio
from pathlib import Path

import pytest

from ankibot.infra.user_preferences import JsonFileUserPreferencesStore, JsonFileUserPreferencesStoreConfig


def make_store(path: Path) -> JsonFileUserPreferencesStore:
    """A store over ``path``, the way the bot would build one at start."""
    return JsonFileUserPreferencesStore(JsonFileUserPreferencesStoreConfig(path=str(path)))


async def test_user_cannot_see_a_deck_or_model_they_never_picked(tmp_path: Path) -> None:
    """With no file yet, an unknown user has no selection of either kind."""
    # Arrange
    store = make_store(tmp_path / "data" / "user_preferences.json")

    # Act
    deck, model = await store.get_deck(user_id=1), await store.get_model(user_id=1)

    # Assert
    assert (deck, model) == (None, None)


async def test_user_can_keep_their_deck_across_a_restart(tmp_path: Path) -> None:
    """A deck picked before a restart is still the user's deck after it."""
    # Arrange
    path = tmp_path / "data" / "user_preferences.json"
    await make_store(path).set_deck(user_id=1, deck_id=10)

    # Act
    selected = await make_store(path).get_deck(user_id=1)

    # Assert
    assert selected == 10


async def test_user_can_keep_their_model_across_a_restart(tmp_path: Path) -> None:
    """A model picked before a restart is still the user's model after it."""
    # Arrange
    path = tmp_path / "user_preferences.json"
    await make_store(path).set_model(user_id=1, model_id="gpt-5-mini")

    # Act
    selected = await make_store(path).get_model(user_id=1)

    # Assert
    assert selected == "gpt-5-mini"


async def test_user_can_change_their_deck(tmp_path: Path) -> None:
    """Picking again replaces the earlier choice, and that is what survives the restart."""
    # Arrange
    path = tmp_path / "user_preferences.json"
    store = make_store(path)
    await store.set_deck(user_id=1, deck_id=10)

    # Act
    await store.set_deck(user_id=1, deck_id=20)

    # Assert
    assert await make_store(path).get_deck(user_id=1) == 20


async def test_user_can_pick_a_model_without_losing_their_deck(tmp_path: Path) -> None:
    """Setting one preference leaves the other as it was, in the file and not only in memory."""
    # Arrange
    path = tmp_path / "user_preferences.json"
    store = make_store(path)
    await store.set_deck(user_id=1, deck_id=10)

    # Act
    await store.set_model(user_id=1, model_id="gpt-5-mini")

    # Assert
    reloaded = make_store(path)
    assert (await reloaded.get_deck(1), await reloaded.get_model(1)) == (10, "gpt-5-mini")


async def test_user_can_pick_a_deck_without_losing_their_model(tmp_path: Path) -> None:
    """The mirror case: a later deck choice keeps the model chosen before it."""
    # Arrange
    path = tmp_path / "user_preferences.json"
    store = make_store(path)
    await store.set_model(user_id=1, model_id="gpt-5-mini")

    # Act
    await store.set_deck(user_id=1, deck_id=10)

    # Assert
    reloaded = make_store(path)
    assert (await reloaded.get_deck(1), await reloaded.get_model(1)) == (10, "gpt-5-mini")


@pytest.mark.parametrize(
    "content",
    ['"not an object"', '{"1": 10}', '{"1": {"deck_id": "ten"}}', '{"1": {"model": 5}}'],
    ids=["not-an-object", "bare-deck-id", "deck-id-not-int", "model-not-str"],
)
async def test_bot_cannot_start_over_a_corrupt_preferences_file(tmp_path: Path, content: str) -> None:
    """A file not shaped as per-user preferences refuses to load, so the bot stops at launch rather than misfile cards.

    The bare ``{"1": 10}`` shape is the retired ``selected_decks.json`` format: it is rejected, not
    read as a deck, so a stale file cannot be mistaken for the current one.
    """
    # Arrange
    path = tmp_path / "user_preferences.json"
    path.write_text(content)

    # Act / Assert
    with pytest.raises(ValueError, match=str(path)):
        make_store(path)


async def test_two_users_can_pick_different_decks_concurrently(tmp_path: Path) -> None:
    """Concurrent choices are keyed per user and both reach the file; neither overwrites the other's deck."""
    # Arrange
    path = tmp_path / "user_preferences.json"
    store = make_store(path)

    async def pick(user_id: int, deck_id: int) -> None:
        await store.set_deck(user_id, deck_id)
        await asyncio.sleep(0)

    # Act
    await asyncio.gather(pick(1, 10), pick(2, 20))

    # Assert
    reloaded = make_store(path)
    assert (await reloaded.get_deck(1), await reloaded.get_deck(2)) == (10, 20)


async def test_one_user_can_pick_a_deck_and_a_model_concurrently(tmp_path: Path) -> None:
    """Two preferences of one user written at once both reach the file; neither write drops the other's field."""
    # Arrange
    path = tmp_path / "user_preferences.json"
    store = make_store(path)

    async def pick_deck() -> None:
        await store.set_deck(1, 10)
        await asyncio.sleep(0)

    async def pick_model() -> None:
        await store.set_model(1, "gpt-5-mini")
        await asyncio.sleep(0)

    # Act
    await asyncio.gather(pick_deck(), pick_model())

    # Assert
    reloaded = make_store(path)
    assert (await reloaded.get_deck(1), await reloaded.get_model(1)) == (10, "gpt-5-mini")
