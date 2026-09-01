import logging

from aiogram import Router
from aiogram.types import ErrorEvent

from ankibot.presentation.identity import NoTelegramUserError

logger = logging.getLogger(__name__)

router = Router()


@router.errors()
async def unexpected_error_handler(event: ErrorEvent) -> None:
    """Last-resort handler for exceptions no command handler caught, so the user is never left silent."""
    message = event.update.message

    # An update with no sender is an expected shape, not a fault: it reaches here only because the
    # user id is resolved as a dependency, before the handler body can run and catch anything.
    if isinstance(event.exception, NoTelegramUserError):
        logger.info(
            "Update %s carried no sender to attribute it to",
            event.update.update_id,
            extra={"update_id": event.update.update_id},
        )
        if message is not None:
            await message.answer(
                "I can't tell who you are here. Send the command from your own account in a private chat."
            )
        return

    logger.error(
        "Unhandled error while processing update %s",
        event.update.update_id,
        exc_info=event.exception,
        extra={"update_id": event.update.update_id},
    )

    if message is not None:
        await message.answer("Something went wrong. Please try again later.")
