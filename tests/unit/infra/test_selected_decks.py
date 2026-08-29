"""The in-process store behind every user's deck choice.

It is shared mutable state, so it gets the concurrency test AGENTS.md requires of one.
"""

import asyncio

from ankibot.infra.selected_decks import InMemorySelectedDeckStore


async def test_user_cannot_see_a_deck_they_never_picked() -> None:
    """An unknown user has no selection, so the bot falls back to AnkiWeb's current deck."""
    # Arrange
    store = InMemorySelectedDeckStore()

    # Act
    selected = await store.get(user_id=1)

    # Assert
    assert selected is None


async def test_two_users_can_pick_different_decks_concurrently() -> None:
    """Concurrent choices are keyed per user, so neither overwrites the other's deck."""
    # Arrange
    store = InMemorySelectedDeckStore()

    async def pick(user_id: int, deck_id: int) -> int | None:
        await store.set(user_id, deck_id)
        await asyncio.sleep(0)
        return await store.get(user_id)

    # Act
    first, second = await asyncio.gather(pick(1, 10), pick(2, 20))

    # Assert
    assert (first, second) == (10, 20)
