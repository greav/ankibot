"""Middleware for bot authorization and other checks."""

import logging
from typing import Any, Awaitable, Callable, Dict, List

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)


class AdminOnlyMiddleware(BaseMiddleware):
    """Middleware to allow only admin users to use the bot."""

    def __init__(self, admin_user_ids: List[int]) -> None:
        """Initialize middleware with admin user IDs."""
        self.admin_user_ids = set(admin_user_ids) if admin_user_ids else set()
        logger.info(f"Admin-only mode enabled for user IDs: {self.admin_user_ids}")

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Check if user is admin before processing the message."""
        if isinstance(event, Message):
            if not event.from_user:
                return  # Skip if no user info

            user_id = event.from_user.id

            # If admin list is empty, allow everyone (fallback for development)
            if not self.admin_user_ids:
                logger.warning("No admin user IDs configured - allowing all users")
                return await handler(event, data)

            # Check if user is admin
            if user_id not in self.admin_user_ids:
                username = event.from_user.username or "unknown"
                logger.warning(f"Unauthorized access attempt by user {user_id} (@{username})")
                await event.answer(
                    "🚫 **Access Denied**\n\n"
                    "Sorry, this bot is private and only available to authorized users.\n\n"
                    "If you believe this is an error, please contact the bot administrator."
                )
                return  # Don't process the message further

            logger.info(f"Authorized user {user_id} (@{event.from_user.username}) accessing bot")

        return await handler(event, data)
