"""The container the handler tests run over: production's interactors, in-process ports.

``InteractorProvider`` and ``IdentityProvider`` are the production ones on purpose — the graph under
test is the graph ``main()`` builds, and only what would leave the process is substituted. The fakes
come from fixtures rather than from a factory here, so a test can still steer the one it is about to
exercise before feeding its update.

Shaped like production's ``ConfigProvider``: the values arrive through ``__init__`` and each is
handed out by a typed method, so mypy checks that what is registered under a port really is one.
"""

from dishka import STRICT_VALIDATION, AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.aiogram import AiogramProvider

from ankibot.application.add_snippet_cards import SnippetCardsGenerator
from ankibot.application.add_vocabulary_word import CardGenerator, VocabularyCardGateway
from ankibot.application.anki_authentication.authenticate_anki import AnkiAuthenticator
from ankibot.application.common.card_gateway import CardGateway
from ankibot.application.common.selected_deck_store import SelectedDeckStore
from ankibot.application.manage_decks.ports import DeckGateway
from ankibot.bootstrap.di.providers import IdentityProvider, InteractorProvider


class FakePortProvider(Provider):
    """Every port the interactors depend on, answered by the fake the fixtures built."""

    scope = Scope.APP

    def __init__(
        self,
        *,
        authenticator: AnkiAuthenticator,
        card_gateway: CardGateway,
        deck_gateway: DeckGateway,
        selected_decks: SelectedDeckStore,
        vocabulary_card_gateway: VocabularyCardGateway,
        card_generator: CardGenerator,
        snippet_cards_generator: SnippetCardsGenerator,
    ) -> None:
        super().__init__()
        self._authenticator = authenticator
        self._card_gateway = card_gateway
        self._deck_gateway = deck_gateway
        self._selected_decks = selected_decks
        self._vocabulary_card_gateway = vocabulary_card_gateway
        self._card_generator = card_generator
        self._snippet_cards_generator = snippet_cards_generator

    @provide
    def anki_authenticator(self) -> AnkiAuthenticator:
        return self._authenticator

    @provide
    def card_gateway(self) -> CardGateway:
        return self._card_gateway

    @provide
    def deck_gateway(self) -> DeckGateway:
        return self._deck_gateway

    @provide
    def selected_deck_store(self) -> SelectedDeckStore:
        return self._selected_decks

    @provide
    def vocabulary_card_gateway(self) -> VocabularyCardGateway:
        return self._vocabulary_card_gateway

    @provide
    def card_generator(self) -> CardGenerator:
        return self._card_generator

    @provide
    def snippet_cards_generator(self) -> SnippetCardsGenerator:
        return self._snippet_cards_generator


def make_fake_container(
    *,
    authenticator: AnkiAuthenticator,
    card_gateway: CardGateway,
    deck_gateway: DeckGateway,
    selected_decks: SelectedDeckStore,
    vocabulary_card_gateway: VocabularyCardGateway,
    card_generator: CardGenerator,
    snippet_cards_generator: SnippetCardsGenerator,
) -> AsyncContainer:
    """Build the test container over the given fakes, under the same validation production uses."""
    return make_async_container(
        FakePortProvider(
            authenticator=authenticator,
            card_gateway=card_gateway,
            deck_gateway=deck_gateway,
            selected_decks=selected_decks,
            vocabulary_card_gateway=vocabulary_card_gateway,
            card_generator=card_generator,
            snippet_cards_generator=snippet_cards_generator,
        ),
        InteractorProvider(),
        AiogramProvider(),
        IdentityProvider(),
        validation_settings=STRICT_VALIDATION,
    )
