"""Fetching the image a user sent, shared by every handler module that accepts one.

Router-free like ``deck_picker``: the snippet-cards and vocabulary-word flows both download images,
and a module owning a ``Router`` cannot be imported by another handler module.
"""

from aiogram import Bot

from ankibot.application.common.dto.image import Image

# Telegram recompresses every photo-style upload to JPEG; only a document keeps its own type.
PHOTO_JPEG_MIME = "image/jpeg"


async def download_image(bot: Bot, file_id: str, mime_type: str) -> Image | None:
    """Fetch the sent image's bytes, or None when Telegram hands nothing back."""
    buffer = await bot.download(file_id)
    if buffer is None:
        return None
    return Image(data=buffer.read(), mime_type=mime_type)
