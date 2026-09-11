"""Which update a log line belongs to, stamped once for every update.

Router-free like ``access``: an outer middleware on the dispatcher's ``update`` observer, so every
line logged while an update is handled — by a handler, an interactor or an adapter underneath —
carries that update's id through ``request_id_var``, and the lines of one update read together.
"""

from collections.abc import Awaitable, Callable
from typing import Any, override

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from ankibot.infra.logger import request_id_var


class CorrelationMiddleware(BaseMiddleware):
    """Stamps the update's id on every log line written while it is handled."""

    @override
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)
        token = request_id_var.set(str(event.update_id))
        try:
            return await handler(event, data)
        finally:
            request_id_var.reset(token)
