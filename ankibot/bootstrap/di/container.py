"""The composition root: the providers the bot runs on, and the validation they are built under."""

from dishka import STRICT_VALIDATION, AsyncContainer, make_async_container
from dishka.integrations.aiogram import AiogramProvider

from ankibot.bootstrap.config import Config
from ankibot.bootstrap.di.providers import (
    AdapterProvider,
    ConfigProvider,
    IdentityProvider,
    InteractorProvider,
)


def make_container(config: Config) -> AsyncContainer:
    """Build the production container.

    ``STRICT_VALIDATION`` makes an incomplete graph a startup failure rather than a ``TypeError``
    on whichever update first reaches the handler that needed the missing dependency.
    """
    return make_async_container(
        ConfigProvider(config),
        AdapterProvider(),
        InteractorProvider(),
        # Supplies the update itself to the REQUEST scope, which is what IdentityProvider reads.
        AiogramProvider(),
        IdentityProvider(),
        validation_settings=STRICT_VALIDATION,
    )
