from collections.abc import AsyncIterator

import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dishka import AsyncContainer

from ankibot.application.add_snippet_cards import DraftCard
from ankibot.application.manage_decks import Deck
from ankibot.bootstrap.bot import create_dispatcher
from tests.common.fakes.anki_authenticator import FakeAnkiAuthenticator
from tests.common.fakes.card_gateway import FakeCardGateway
from tests.common.fakes.card_generator import FakeCardGenerator
from tests.common.fakes.deck_gateway import FakeDeckGateway
from tests.common.fakes.ports import make_fake_container
from tests.common.fakes.selected_deck_store import FakeSelectedDeckStore
from tests.common.fakes.snippet_cards_generator import FakeSnippetCardsGenerator
from tests.common.fakes.vocabulary_card_gateway import DEFAULT_TEMPLATE, FakeVocabularyCardGateway

DEFAULT_DECKS = {1: "Default", 2: "Spanish"}
DEFAULT_DECK_ID = 1
DEFAULT_GENERATED_VALUES = {"Word": "serendipity", "Meaning": "a pleasant surprise", "Example": "What a serendipity!"}
DEFAULT_SNIPPET_CARDS = [
    DraftCard(front="What does GIL stand for?", back="Global Interpreter Lock"),
    DraftCard(front="Which lock serializes Python bytecode execution?", back="The GIL"),
]


def default_deck_list() -> list[Deck]:
    return [Deck(id=deck_id, name=name) for deck_id, name in DEFAULT_DECKS.items()]


@pytest.fixture(scope="session")
def authenticator() -> FakeAnkiAuthenticator:
    """The fake behind the dispatcher's interactor; a test sets ``error`` to steer its own run.

    Session-scoped because the dispatcher below is, which is the one exception AGENTS.md allows to
    the per-test scope rule. It holds only while ``reset_authenticator`` keeps running.
    """
    return FakeAnkiAuthenticator()


@pytest.fixture(scope="session")
def card_gateway() -> FakeCardGateway:
    """The fake behind the dispatcher's CreateCard interactor; a test sets its fields to steer its own run.

    Session-scoped for the same reason as ``authenticator`` above; ``reset_card_gateway`` restores
    it before every test.
    """
    return FakeCardGateway(decks=dict(DEFAULT_DECKS), current_deck_id=DEFAULT_DECK_ID)


@pytest.fixture(scope="session")
def deck_gateway() -> FakeDeckGateway:
    """The fake behind the deck interactors; ``reset_deck_gateway`` restores it before every test."""
    return FakeDeckGateway(decks=default_deck_list())


@pytest.fixture(scope="session")
def selected_decks() -> FakeSelectedDeckStore:
    """The deck choices behind the dispatcher; ``reset_selected_decks`` clears them per test."""
    return FakeSelectedDeckStore()


@pytest.fixture(scope="session")
def vocabulary_card_gateway() -> FakeVocabularyCardGateway:
    """The fake behind GenerateCard/SaveCard; ``reset_vocabulary_card_gateway`` restores it per test."""
    return FakeVocabularyCardGateway()


@pytest.fixture(scope="session")
def card_generator() -> FakeCardGenerator:
    """The fake behind GenerateCard's LLM call; ``reset_card_generator`` restores it per test."""
    return FakeCardGenerator(values=dict(DEFAULT_GENERATED_VALUES))


@pytest.fixture(scope="session")
def snippet_cards_generator() -> FakeSnippetCardsGenerator:
    """The fake behind GenerateCards' LLM call; ``reset_snippet_cards_generator`` restores it per test."""
    return FakeSnippetCardsGenerator(cards=list(DEFAULT_SNIPPET_CARDS))


@pytest.fixture(scope="session")
async def container(
    authenticator: FakeAnkiAuthenticator,
    card_gateway: FakeCardGateway,
    deck_gateway: FakeDeckGateway,
    selected_decks: FakeSelectedDeckStore,
    vocabulary_card_gateway: FakeVocabularyCardGateway,
    card_generator: FakeCardGenerator,
    snippet_cards_generator: FakeSnippetCardsGenerator,
) -> AsyncIterator[AsyncContainer]:
    """Production's interactor graph over the fakes above, validated as strictly as production is."""
    container = make_fake_container(
        authenticator=authenticator,
        card_gateway=card_gateway,
        deck_gateway=deck_gateway,
        selected_decks=selected_decks,
        vocabulary_card_gateway=vocabulary_card_gateway,
        card_generator=card_generator,
        snippet_cards_generator=snippet_cards_generator,
    )
    yield container
    await container.close()


@pytest.fixture(scope="session")
def dispatcher(container: AsyncContainer) -> Dispatcher:
    """The real dispatcher, composed exactly as the bot composes it.

    Built once per session because a handler module's ``Router`` is a module-level singleton:
    including it a second time raises ``RuntimeError: Router is already attached``.
    """
    return create_dispatcher(container)


@pytest.fixture(autouse=True)
def reset_authenticator(authenticator: FakeAnkiAuthenticator) -> None:
    """Undo whatever the previous test asked the shared authenticator to do."""
    authenticator.error = None


@pytest.fixture(autouse=True)
def reset_card_gateway(card_gateway: FakeCardGateway) -> None:
    """Undo whatever the previous test asked the shared card gateway to do."""
    card_gateway.decks = dict(DEFAULT_DECKS)
    card_gateway.current_deck_id = DEFAULT_DECK_ID
    card_gateway.notetype_id = 1
    card_gateway.field_count = 2
    card_gateway.error = None
    card_gateway.fail_add_after = None
    card_gateway.reset_added()


@pytest.fixture(autouse=True)
def reset_deck_gateway(deck_gateway: FakeDeckGateway) -> None:
    """Undo whatever the previous test asked the shared deck gateway to do."""
    deck_gateway.decks = default_deck_list()
    deck_gateway.error = None


@pytest.fixture(autouse=True)
def reset_selected_decks(selected_decks: FakeSelectedDeckStore) -> None:
    """Drop the deck choices the previous test made, so none leaks into this one."""
    selected_decks.decks.clear()


@pytest.fixture(autouse=True)
def reset_vocabulary_card_gateway(vocabulary_card_gateway: FakeVocabularyCardGateway) -> None:
    """Undo whatever the previous test asked the shared vocabulary card gateway to do."""
    vocabulary_card_gateway.deck_id = 1
    vocabulary_card_gateway.deck_name = "English Words V2"
    vocabulary_card_gateway.notetype_id = 1
    vocabulary_card_gateway.template = DEFAULT_TEMPLATE
    vocabulary_card_gateway.error = None


@pytest.fixture(autouse=True)
def reset_card_generator(card_generator: FakeCardGenerator) -> None:
    """Undo whatever the previous test asked the shared card generator to do."""
    card_generator.values = dict(DEFAULT_GENERATED_VALUES)
    card_generator.error = None


@pytest.fixture(autouse=True)
def reset_snippet_cards_generator(snippet_cards_generator: FakeSnippetCardsGenerator) -> None:
    """Undo whatever the previous test asked the shared snippet-cards generator to do."""
    snippet_cards_generator.cards = list(DEFAULT_SNIPPET_CARDS)
    snippet_cards_generator.error = None


@pytest.fixture(autouse=True)
def reset_fsm_storage(dispatcher: Dispatcher) -> None:
    """Install a fresh FSM storage before every test, so state cannot leak between tests.

    Mandatory alongside the resets above: the dispatcher is session-scoped only because handler
    ``Router``s are module singletons, and a stale ``MemoryStorage`` would otherwise carry one
    test's FSM state into the next.
    """
    dispatcher.fsm.storage = MemoryStorage()
