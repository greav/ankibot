import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from ankibot.application.anki_authentication import AuthenticateAnki
from ankibot.application.manage_cards import CreateCard
from ankibot.application.manage_cards.create_card import AddTarget
from ankibot.bootstrap.bot import create_dispatcher
from tests.common.fakes.anki_authenticator import FakeAnkiAuthenticator
from tests.common.fakes.card_gateway import FakeCardGateway


@pytest.fixture(scope="session")
def authenticator() -> FakeAnkiAuthenticator:
    """The fake behind the dispatcher's interactor; a test sets ``error`` to steer its own run.

    Session-scoped because the dispatcher below is, which is the one exception AGENTS.md allows to
    the per-test scope rule. It holds only while ``reset_authenticator`` keeps running.
    """
    return FakeAnkiAuthenticator()


@pytest.fixture(scope="session")
def card_gateway() -> FakeCardGateway:
    """The fake behind the dispatcher's CreateCard interactor; a test sets ``target``/``error``
    to steer its own run.

    Session-scoped for the same reason as ``authenticator`` above; ``reset_card_gateway`` restores
    it before every test.
    """
    return FakeCardGateway(target=AddTarget(deck_id=1, notetype_id=1, deck_name="Default", field_count=2))


@pytest.fixture(scope="session")
def dispatcher(authenticator: FakeAnkiAuthenticator, card_gateway: FakeCardGateway) -> Dispatcher:
    """The real dispatcher, composed exactly as the bot composes it.

    Built once per session because a handler module's ``Router`` is a module-level singleton:
    including it a second time raises ``RuntimeError: Router is already attached``.
    """
    return create_dispatcher(AuthenticateAnki(authenticator), CreateCard(card_gateway))


@pytest.fixture(autouse=True)
def reset_authenticator(authenticator: FakeAnkiAuthenticator) -> None:
    """Undo whatever the previous test asked the shared authenticator to do."""
    authenticator.error = None


@pytest.fixture(autouse=True)
def reset_card_gateway(card_gateway: FakeCardGateway) -> None:
    """Undo whatever the previous test asked the shared card gateway to do."""
    card_gateway.target = AddTarget(deck_id=1, notetype_id=1, deck_name="Default", field_count=2)
    card_gateway.error = None


@pytest.fixture(autouse=True)
def reset_fsm_storage(dispatcher: Dispatcher) -> None:
    """Install a fresh FSM storage before every test, so state cannot leak between tests.

    Mandatory alongside the two resets above: the dispatcher is session-scoped only because
    handler ``Router``s are module singletons, and a stale ``MemoryStorage`` would otherwise carry
    one test's FSM state into the next.
    """
    dispatcher.fsm.storage = MemoryStorage()
