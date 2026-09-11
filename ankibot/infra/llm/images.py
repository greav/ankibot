"""How an image reaches an OpenAI chat completion: as a ``data:`` URL in an image part."""

import base64

from ankibot.application.common.dto.image import Image


def image_data_url(image: Image) -> str:
    """``image`` as the ``data:`` URL an OpenAI image part carries."""
    encoded = base64.b64encode(image.data).decode("ascii")
    return f"data:{image.mime_type};base64,{encoded}"
