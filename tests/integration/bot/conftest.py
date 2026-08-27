import pytest
from aiogram import Dispatcher

from ankibot.application.anki_authentication import AuthenticateAnki
from ankibot.bootstrap.bot import create_dispatcher
from tests.common.fakes.anki_authenticator import FakeAnkiAuthenticator


@pytest.fixture(scope="session")
def authenticator() -> FakeAnkiAuthenticator:
    """The fake behind the dispatcher's interactor; a test sets ``error`` to steer its own run.

    Session-scoped because the dispatcher below is, which is the one exception AGENTS.md allows to
    the per-test scope rule. It holds only while ``reset_authenticator`` keeps running.
    """
    return FakeAnkiAuthenticator()


@pytest.fixture(scope="session")
def dispatcher(authenticator: FakeAnkiAuthenticator) -> Dispatcher:
    """The real dispatcher, composed exactly as the bot composes it.

    Built once per session because a handler module's ``Router`` is a module-level singleton:
    including it a second time raises ``RuntimeError: Router is already attached``.
    """
    return create_dispatcher(AuthenticateAnki(authenticator))


@pytest.fixture(autouse=True)
def reset_authenticator(authenticator: FakeAnkiAuthenticator) -> None:
    """Undo whatever the previous test asked the shared authenticator to do."""
    authenticator.error = None
