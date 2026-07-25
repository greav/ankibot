import logging

from aiogram import Router
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)

router = Router()


@router.errors()
async def unexpected_error_handler(event: ErrorEvent) -> None:
    """Last-resort handler for exceptions no command handler caught, so the user is never left silent."""
    logger.error(
        "Unhandled error while processing update",
        exc_info=event.exception,
        extra={"update_id": event.update.update_id},
    )

    message = event.update.message
    if message is not None:
        await message.answer("Something went wrong. Please try again later.")
