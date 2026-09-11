"""The correlation middleware is called directly: what it guarantees is the value ``request_id_var``
holds while the handler runs, which the dispatcher tests cannot observe — the log formatter reads
the variable at format time, after the middleware has already reset it."""

from typing import Any

from aiogram.types import TelegramObject, Update

from ankibot.infra.logger import request_id_var
from ankibot.presentation.middlewares.correlation import CorrelationMiddleware


async def test_operator_can_read_the_lines_of_one_update_together() -> None:
    """While an update is handled the request id is its update_id; afterwards it is back to NA."""
    # Arrange
    seen: list[str] = []

    async def handler(_event: TelegramObject, _data: dict[str, Any]) -> None:
        seen.append(request_id_var.get())

    # Act
    await CorrelationMiddleware()(handler, Update(update_id=42), {})

    # Assert
    assert seen == ["42"]
    assert request_id_var.get() == "NA"
