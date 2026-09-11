"""Every per-class config dataclass the graph resolves, taken apart from the loaded ``Config``.

Each class keeps taking its own config dataclass first; what changes
is that nobody routes those dataclasses by hand. This provider states once, per type, which field it
comes from — and mypy checks each statement, which a ``{type: value}`` context mapping cannot: there
the key and the value are unrelated as far as the type checker is concerned.

The root ``Config`` is deliberately not provided: destructuring it here is what keeps it out of the
graph, so no factory below can ask for it.
"""

from dishka import Provider, Scope, provide

from ankibot.bootstrap.config import CardGeneratorConfig, Config
from ankibot.infra.anki.authenticator import AnkiWebAuthenticatorConfig
from ankibot.infra.anki.svc import AnkiSvcClientConfig
from ankibot.infra.anki.vocabulary_card_gateway import AnkiWebVocabularyCardGatewayConfig
from ankibot.infra.llm.openai_client import OpenAIClientConfig
from ankibot.infra.llm.snippet_cards.openai_snippet_cards_generator import OpenAISnippetCardsGeneratorConfig
from ankibot.infra.llm.vocabulary_card.openai_card_generator import OpenAICardGeneratorConfig
from ankibot.infra.llm.vocabulary_card.openai_word_suggester import OpenAIWordSuggesterConfig
from ankibot.infra.selected_decks import JsonFileSelectedDeckStoreConfig


class ConfigProvider(Provider):
    """Exposes the loaded configuration's per-class dataclasses, resolved by type."""

    scope = Scope.APP

    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config

    @provide
    def anki_web(self) -> AnkiWebAuthenticatorConfig:
        return self._config.anki_web

    @provide
    def anki_svc(self) -> AnkiSvcClientConfig:
        return self._config.anki_svc

    @provide
    def anki_vocabulary_cards(self) -> AnkiWebVocabularyCardGatewayConfig:
        return self._config.anki_vocabulary_cards

    @provide
    def selected_decks(self) -> JsonFileSelectedDeckStoreConfig:
        return self._config.selected_decks

    @provide
    def card_generator_choice(self) -> CardGeneratorConfig:
        return self._config.card_generator

    @provide
    def openai_client(self) -> OpenAIClientConfig:
        return self._config.openai_client

    @provide
    def openai_card_generator(self) -> OpenAICardGeneratorConfig:
        return self._config.openai_card_generator

    @provide
    def openai_word_suggester(self) -> OpenAIWordSuggesterConfig:
        return self._config.openai_word_suggester

    @provide
    def openai_snippet_cards(self) -> OpenAISnippetCardsGeneratorConfig:
        return self._config.openai_snippet_cards
