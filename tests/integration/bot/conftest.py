from collections.abc import AsyncIterator

import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dishka import AsyncContainer

from ankibot.application.add_snippet_cards import DraftCard
from ankibot.application.common.model_catalog import ModelOption
from ankibot.application.manage_decks import Deck
from ankibot.bootstrap.bot import create_dispatcher
from ankibot.presentation.middlewares.access import AccessConfig
from tests.common.fakes.anki_authenticator import FakeAnkiAuthenticator
from tests.common.fakes.card_gateway import FakeCardGateway
from tests.common.fakes.card_generator import FakeCardGenerator
from tests.common.fakes.deck_gateway import FakeDeckGateway
from tests.common.fakes.model_catalog import FakeModelCatalog
from tests.common.fakes.ports import make_fake_container
from tests.common.fakes.selected_deck_store import FakeSelectedDeckStore
from tests.common.fakes.selected_model_store import FakeSelectedModelStore
from tests.common.fakes.snippet_cards_generator import FakeSnippetCardsGenerator
from tests.common.fakes.vocabulary_card_gateway import DEFAULT_TEMPLATE, FakeVocabularyCardGateway
from tests.common.fakes.word_suggester import FakeWordSuggester

# Any sender id a test picks must stay at or below this cap to pass the allowlist gate the
# dispatcher fixture builds; ids above it belong to test_access's strangers.
MAX_ALLOWED_TEST_USER_ID = 99

DEFAULT_DECKS = {1: "Default", 2: "Spanish"}
DEFAULT_DECK_ID = 1
DEFAULT_MODEL_OPTIONS = [
    ModelOption(id="gpt-4o-mini", label="GPT-4o mini"),
    ModelOption(id="gpt-5-mini", label="GPT-5 mini"),
]
DEFAULT_MODEL_ID = "gpt-4o-mini"
DEFAULT_GENERATED_VALUES = {"Word": "serendipity", "Meaning": "a pleasant surprise", "Example": "What a serendipity!"}
DEFAULT_SUGGESTED_WORDS = ["serendipity", "ubiquitous"]
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
    return FakeCardGateway(decks=dict(DEFAULT_DECKS))


@pytest.fixture(scope="session")
def deck_gateway() -> FakeDeckGateway:
    """The fake behind the deck interactors; ``reset_deck_gateway`` restores it before every test."""
    return FakeDeckGateway(decks=default_deck_list())


@pytest.fixture(scope="session")
def selected_decks() -> FakeSelectedDeckStore:
    """The deck choices behind the dispatcher; ``reset_selected_decks`` restores them per test."""
    return FakeSelectedDeckStore()


@pytest.fixture(scope="session")
def selected_models() -> FakeSelectedModelStore:
    """The model choices behind the dispatcher; ``reset_selected_models`` empties them per test."""
    return FakeSelectedModelStore()


@pytest.fixture(scope="session")
def model_catalog() -> FakeModelCatalog:
    """The models /model offers; ``reset_model_catalog`` restores the list per test."""
    return FakeModelCatalog(options=list(DEFAULT_MODEL_OPTIONS), default_id=DEFAULT_MODEL_ID)


@pytest.fixture(scope="session")
def vocabulary_card_gateway() -> FakeVocabularyCardGateway:
    """The fake behind GenerateCard/SaveCard; ``reset_vocabulary_card_gateway`` restores it per test."""
    return FakeVocabularyCardGateway()


@pytest.fixture(scope="session")
def card_generator() -> FakeCardGenerator:
    """The fake behind GenerateCard's LLM call; ``reset_card_generator`` restores it per test."""
    return FakeCardGenerator(values=dict(DEFAULT_GENERATED_VALUES))


@pytest.fixture(scope="session")
def word_suggester() -> FakeWordSuggester:
    """The fake behind SuggestWords' LLM call; ``reset_word_suggester`` restores it per test."""
    return FakeWordSuggester(words=list(DEFAULT_SUGGESTED_WORDS))


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
    selected_models: FakeSelectedModelStore,
    model_catalog: FakeModelCatalog,
    vocabulary_card_gateway: FakeVocabularyCardGateway,
    card_generator: FakeCardGenerator,
    word_suggester: FakeWordSuggester,
    snippet_cards_generator: FakeSnippetCardsGenerator,
) -> AsyncIterator[AsyncContainer]:
    """Production's interactor graph over the fakes above, validated as strictly as production is."""
    container = make_fake_container(
        authenticator=authenticator,
        card_gateway=card_gateway,
        deck_gateway=deck_gateway,
        selected_decks=selected_decks,
        selected_models=selected_models,
        model_catalog=model_catalog,
        vocabulary_card_gateway=vocabulary_card_gateway,
        card_generator=card_generator,
        word_suggester=word_suggester,
        snippet_cards_generator=snippet_cards_generator,
    )
    yield container
    await container.close()


@pytest.fixture(scope="session")
def dispatcher(container: AsyncContainer) -> Dispatcher:
    """The real dispatcher, composed exactly as the bot composes it.

    Built once per session because a handler module's ``Router`` is a module-level singleton:
    including it a second time raises ``RuntimeError: Router is already attached``.

    The allowlist admits every id up to ``MAX_ALLOWED_TEST_USER_ID``: the builders default to
    ``TEST_USER_ID`` and tests hand-pick other small ids for multi-user scenarios, so any of those
    doubles as the allowed-user path through the gate. ``test_access`` plays the stranger with an
    id above the cap.
    """
    access = AccessConfig(allowed_user_ids=",".join(str(i) for i in range(1, MAX_ALLOWED_TEST_USER_ID + 1)))
    return create_dispatcher(container, access)


@pytest.fixture(autouse=True)
def reset_authenticator(authenticator: FakeAnkiAuthenticator) -> None:
    """Undo whatever the previous test asked the shared authenticator to do."""
    authenticator.error = None


@pytest.fixture(autouse=True)
def reset_card_gateway(card_gateway: FakeCardGateway) -> None:
    """Undo whatever the previous test asked the shared card gateway to do."""
    card_gateway.decks = dict(DEFAULT_DECKS)
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
    """Start every allowed user on the Default deck, so a test about the deck itself picks another.

    Nothing writes a card without a chosen deck, so an empty store would make every card test
    begin with /decks; a test about the missing choice drops its own user instead.
    """
    selected_decks.decks = dict.fromkeys(range(1, MAX_ALLOWED_TEST_USER_ID + 1), DEFAULT_DECK_ID)


@pytest.fixture(autouse=True)
def reset_selected_models(selected_models: FakeSelectedModelStore) -> None:
    """Start every test with nobody having picked a model, so the catalog's default serves them."""
    selected_models.models.clear()


@pytest.fixture(autouse=True)
def reset_model_catalog(model_catalog: FakeModelCatalog) -> None:
    """Undo whatever the previous test asked the shared catalog to offer."""
    model_catalog.options_list = list(DEFAULT_MODEL_OPTIONS)
    model_catalog.default_id = DEFAULT_MODEL_ID


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
def reset_word_suggester(word_suggester: FakeWordSuggester) -> None:
    """Undo whatever the previous test asked the shared word suggester to do."""
    word_suggester.words = list(DEFAULT_SUGGESTED_WORDS)
    word_suggester.error = None


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
