"""Who the current update is from, resolved once per update.

REQUEST-scoped, so the answer is computed at most once per update and can grow into a lookup of our
own user record without a single handler signature changing.
"""

from aiogram.types import TelegramObject
from dishka import Provider, Scope, provide

from ankibot.presentation.identity import TelegramUserId, telegram_user_id


class IdentityProvider(Provider):
    """Turns the update dishka's aiogram middleware puts in the context into a user id."""

    scope = Scope.REQUEST

    @provide
    def user_id(self, event: TelegramObject) -> TelegramUserId:
        """Raise ``NoTelegramUserError`` when the update has no sender to attribute it to."""
        return telegram_user_id(event)
