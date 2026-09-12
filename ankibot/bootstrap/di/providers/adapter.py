"""The infrastructure half of the graph: one factory per adapter, all APP-scoped."""

from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, WithParents, provide
from openai import AsyncOpenAI

from ankibot.infra.anki.authenticator import AnkiWebAuthenticator
from ankibot.infra.anki.card_gateway import AnkiWebCardGateway
from ankibot.infra.anki.deck_gateway import AnkiWebDeckGateway
from ankibot.infra.anki.svc import AnkiSvcClient
from ankibot.infra.anki.vocabulary_card_gateway import AnkiWebVocabularyCardGateway
from ankibot.infra.llm.catalog import ConfigModelCatalog
from ankibot.infra.llm.openai_client import OpenAIClientConfig, build_openai_client
from ankibot.infra.llm.snippet_cards.openai_snippet_cards_generator import OpenAISnippetCardsGenerator
from ankibot.infra.llm.vocabulary_card.openai_card_generator import OpenAICardGenerator
from ankibot.infra.llm.vocabulary_card.openai_word_suggester import OpenAIWordSuggester
from ankibot.infra.user_preferences import JsonFileUserPreferencesStore

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
    # One adapter under both ports: the deck and the model choice share a file.
    user_preferences = provide(WithParents[JsonFileUserPreferencesStore])
    model_catalog = provide(WithParents[ConfigModelCatalog])
    # The model is a per-call argument the interactor resolves, so the adapters need no choice of
    # provider here; a second provider's adapters would slot in as routing adapters under the
    # same ports.
    card_generator = provide(WithParents[OpenAICardGenerator])
    word_suggester = provide(WithParents[OpenAIWordSuggester])
    snippet_cards_generator = provide(WithParents[OpenAISnippetCardsGenerator])

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
