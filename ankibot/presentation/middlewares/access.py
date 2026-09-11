"""Who may use the bot at all, decided once for every update.

Router-free like ``identity``: the allowlist gate is an outer middleware on the dispatcher's
``update`` observer, so it covers every update type — messages, callback queries, whatever a future
router listens to — without any router opting in. It decides admission only; who the sender *is*
stays ``identity``'s job.

A stranger gets silence, not a refusal: for a personal bot, answering at all advertises that the
bot exists and invites retries. A senderless update (a channel post, an anonymous group admin)
cannot be attributed to anyone, so it passes through to the ``NoTelegramUserError`` flow, which
answers it honestly instead of gating it.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from ankibot.presentation.identity import NoTelegramUserError, TelegramUserId, telegram_user_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AccessConfig:
    # Comma-separated Telegram user ids. No default on purpose: the bot must not start open
    # because a config line went missing.
    allowed_user_ids: str


def parse_allowed_user_ids(raw: str) -> frozenset[TelegramUserId]:
    """The allowlist a raw comma-separated config value describes.

    Raises ``ValueError`` on a blank string — an empty allowlist would lock everyone out, which is
    a misconfiguration that should stop the bot on launch, not surface as universal silence — and
    on any entry that is not an integer.
    """
    ids = frozenset(TelegramUserId(int(entry)) for entry in raw.split(",") if entry.strip())
    if not ids:
        msg = "The allowlist is empty; list at least one Telegram user id"
        raise ValueError(msg)
    return ids


class AllowlistMiddleware(BaseMiddleware):
    """Silently drops any update whose sender is not on the allowlist."""

    def __init__(self, config: AccessConfig) -> None:
        # Parsed here so a bad value stops the bot at construction, before polling starts.
        self._allowed = parse_allowed_user_ids(config.allowed_user_ids)

    @override
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Registered on ``dp.update``, so ``event`` is always an ``Update``; the sender sits on the
        # inner event it wraps. The base class fixes this signature, hence the narrowing here.
        inner = event.event if isinstance(event, Update) else event
        try:
            user_id = telegram_user_id(inner)
        except NoTelegramUserError:
            return await handler(event, data)

        if user_id not in self._allowed:
            logger.warning("Dropped an update from user %s not on the allowlist", user_id)
            return None

        return await handler(event, data)
