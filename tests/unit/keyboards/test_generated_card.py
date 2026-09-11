"""``GeneratedCardCallback`` is the one thing here that decides something under a hard limit.

The keyboard itself is a static markup; ``page_of``-style paging does not apply.
"""

from ankibot.presentation.keyboards.generated_card import GeneratedCardCallback

TELEGRAM_CALLBACK_DATA_LIMIT = 64


def test_every_action_stays_within_telegrams_callback_data_limit() -> None:
    """Each action packs well under Telegram's 64-byte callback_data limit."""
    # Arrange / Act
    packed = [GeneratedCardCallback(action=action).pack() for action in ("save", "regenerate", "feedback", "cancel")]

    # Assert
    assert all(len(data.encode()) <= TELEGRAM_CALLBACK_DATA_LIMIT for data in packed)
