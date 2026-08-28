from google.protobuf.message import DecodeError, Message

from ankibot.application.exceptions.base import ApplicationError

PROTOBUF_CONTENT_TYPE = "application/octet-stream"


def parse_or_raise[M: Message](message: M, content: bytes, error: ApplicationError) -> M:
    """Parse ``content`` into ``message``, raising ``error`` instead of a raw ``DecodeError``.

    A 200 carrying HTML (error page, captcha, maintenance page) decodes as garbage protobuf; without
    this, ``DecodeError`` escapes the ``ApplicationError`` hierarchy and the caller gets silence.
    """
    try:
        message.ParseFromString(content)
    except DecodeError as decode_error:
        raise error from decode_error
    return message
