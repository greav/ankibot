"""The /model keyboard's one risk: the catalog id rides in ``callback_data`` under Telegram's 64-byte cap."""

from ankibot.presentation.keyboards.models import ModelCallback

TELEGRAM_CALLBACK_DATA_LIMIT = 64
LONG_MODEL_ID = "x" * 50


def test_user_cannot_overflow_telegrams_callback_data_limit_with_a_long_model_id() -> None:
    """A 50-character id, longer than any provider's today, still packs within the limit.

    aiogram raises ``ValueError`` past it, which only shows in production; this pins the margin.
    """
    # Arrange / Act
    packed = ModelCallback(id=LONG_MODEL_ID).pack()

    # Assert
    assert len(packed.encode()) <= TELEGRAM_CALLBACK_DATA_LIMIT
