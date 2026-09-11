"""The infrastructure half of the graph: one factory per adapter, all APP-scoped."""

from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, WithParents, provide
from openai import AsyncOpenAI

from ankibot.application.add_snippet_cards import SnippetCardsGenerator
from ankibot.application.add_vocabulary_word import CardGenerator, WordSuggester
from ankibot.bootstrap.config import CardGeneratorConfig
from ankibot.infra.anki.authenticator import AnkiWebAuthenticator
from ankibot.infra.anki.card_gateway import AnkiWebCardGateway
from ankibot.infra.anki.deck_gateway import AnkiWebDeckGateway
from ankibot.infra.anki.svc import AnkiSvcClient
from ankibot.infra.anki.vocabulary_card_gateway import AnkiWebVocabularyCardGateway
from ankibot.infra.llm.openai_client import OpenAIClientConfig, build_openai_client
from ankibot.infra.llm.snippet_cards.openai_snippet_cards_generator import (
    OpenAISnippetCardsGenerator,
    OpenAISnippetCardsGeneratorConfig,
)
from ankibot.infra.llm.vocabulary_card.openai_card_generator import OpenAICardGenerator, OpenAICardGeneratorConfig
from ankibot.infra.llm.vocabulary_card.openai_word_suggester import OpenAIWordSuggester, OpenAIWordSuggesterConfig
from ankibot.infra.selected_decks import InMemorySelectedDeckStore

# One client for every AnkiWeb call, because AnkiWeb's session lives in its cookie jar: separate
# clients would each need their own /auth.
HTTP_TIMEOUT_SECONDS = 15.0


class AdapterProvider(Provider):
    """Builds the adapters, and closes the clients they hold when the container closes."""

    scope = Scope.APP

    svc = provide(AnkiSvcClient)
    authenticator = provide(WithParents[AnkiWebAuthenticator])
    card_gateway = provide(WithParents[AnkiWebCardGateway])
    deck_gateway = provide(WithParents[AnkiWebDeckGateway])
    vocabulary_card_gateway = provide(WithParents[AnkiWebVocabularyCardGateway])
    selected_decks = provide(WithParents[InMemorySelectedDeckStore])

    @provide
    async def http_client(self) -> AsyncIterator[httpx.AsyncClient]:
        """The shared HTTP client; whatever is yielded here is closed on container shutdown."""
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            yield client

    @provide
    async def openai_sdk_client(self, config: OpenAIClientConfig) -> AsyncIterator[AsyncOpenAI]:
        """The one SDK client every OpenAI-backed generator shares; closed on container shutdown."""
        client = build_openai_client(config)
        yield client
        await client.close()

    @provide
    def card_generator(
        self,
        choice: CardGeneratorConfig,
        client: AsyncOpenAI,
        generator_config: OpenAICardGeneratorConfig,
    ) -> CardGenerator:
        """The vocabulary-card generator for the configured provider."""
        match choice.provider:
            case "openai":
                return OpenAICardGenerator(generator_config, client)

    @provide
    def word_suggester(
        self,
        choice: CardGeneratorConfig,
        client: AsyncOpenAI,
        suggester_config: OpenAIWordSuggesterConfig,
    ) -> WordSuggester:
        """The screenshot word suggester for the configured provider."""
        match choice.provider:
            case "openai":
                return OpenAIWordSuggester(suggester_config, client)

    @provide
    def snippet_cards_generator(
        self,
        choice: CardGeneratorConfig,
        client: AsyncOpenAI,
        generator_config: OpenAISnippetCardsGeneratorConfig,
    ) -> SnippetCardsGenerator:
        """The snippet-cards generator for the configured provider."""
        match choice.provider:
            case "openai":
                return OpenAISnippetCardsGenerator(generator_config, client)
