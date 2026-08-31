"""The infrastructure half of the graph: one factory per adapter, all APP-scoped."""

from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, WithParents, provide

from ankibot.application.add_vocabulary_word import CardGenerator
from ankibot.bootstrap.config import CardGeneratorConfig
from ankibot.infra.anki.authenticator import AnkiWebAuthenticator
from ankibot.infra.anki.card_gateway import AnkiWebCardGateway
from ankibot.infra.anki.deck_gateway import AnkiWebDeckGateway
from ankibot.infra.anki.svc import AnkiSvcClient
from ankibot.infra.anki.vocabulary_card_gateway import AnkiWebVocabularyCardGateway
from ankibot.infra.llm.openai_client import OpenAIClientConfig, build_openai_client
from ankibot.infra.llm.vocabulary_card.openai_card_generator import OpenAICardGenerator, OpenAICardGeneratorConfig
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
    async def card_generator(
        self,
        choice: CardGeneratorConfig,
        client_config: OpenAIClientConfig,
        generator_config: OpenAICardGeneratorConfig,
    ) -> AsyncIterator[CardGenerator]:
        """The generator for the configured provider, with its SDK client closed on shutdown."""
        match choice.provider:
            case "openai":
                client = build_openai_client(client_config)
                yield OpenAICardGenerator(generator_config, client)
                await client.close()
