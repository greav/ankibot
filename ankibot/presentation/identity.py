"""Who an update is from, and the failure of not being able to tell.

Router-free like ``deck_picker``: every command that keys anything by user reads its id through
here, so the answer is given once instead of at each call site.
"""

from typing import NewType

from aiogram.types import TelegramObject, User

TelegramUserId = NewType("TelegramUserId", int)


class NoTelegramUserError(Exception):
    """The update carries no sender, so nothing about it can be attributed to a user."""


def telegram_user_id(event: TelegramObject) -> TelegramUserId:
    """The Telegram user an update is from.

    ``Message.from_user`` is optional: a channel post, an anonymous group admin's message and an
    automatic forward into a linked group all arrive without a sender. Substituting a placeholder id
    there would file every such update under one user, so the selected deck — and anything else
    keyed by user after it — would be shared between strangers. Refusing is the only honest answer.

    ``getattr`` rather than an attribute access because aiogram declares ``from_user`` on each event
    type separately, with no common base to narrow to.
    """
    user: User | None = getattr(event, "from_user", None)
    if user is None:
        raise NoTelegramUserError
    return TelegramUserId(user.id)
