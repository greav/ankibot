from dataclasses import dataclass
from typing import Literal

from omegaconf import OmegaConf
from pydantic import TypeAdapter

from ankibot.infra.anki.authenticator import AnkiWebAuthenticatorConfig
from ankibot.infra.anki.svc import AnkiSvcClientConfig
from ankibot.infra.anki.vocabulary_card_gateway import AnkiWebVocabularyCardGatewayConfig
from ankibot.infra.llm.openai_client import OpenAIClientConfig
from ankibot.infra.llm.snippet_cards.openai_snippet_cards_generator import OpenAISnippetCardsGeneratorConfig
from ankibot.infra.llm.vocabulary_card.openai_card_generator import OpenAICardGeneratorConfig
from ankibot.infra.llm.vocabulary_card.openai_word_suggester import OpenAIWordSuggesterConfig
from ankibot.infra.logger import LoggerConfig
from ankibot.presentation.middlewares.access import AccessConfig


@dataclass(frozen=True, kw_only=True)
class BotConfig:
    token: str


@dataclass(frozen=True, kw_only=True)
class CardGeneratorConfig:
    # An "anthropic" branch slots in beside "openai" once it exists.
    provider: Literal["openai"]


@dataclass(frozen=True, kw_only=True)
class Config:
    bot: BotConfig
    access: AccessConfig
    logger: LoggerConfig
    anki_web: AnkiWebAuthenticatorConfig
    anki_svc: AnkiSvcClientConfig
    anki_vocabulary_cards: AnkiWebVocabularyCardGatewayConfig
    card_generator: CardGeneratorConfig
    openai_client: OpenAIClientConfig
    openai_card_generator: OpenAICardGeneratorConfig
    openai_word_suggester: OpenAIWordSuggesterConfig
    openai_snippet_cards: OpenAISnippetCardsGeneratorConfig


def load_config(path: str) -> Config:
    conf = OmegaConf.to_container(OmegaConf.load(path), resolve=True)

    return TypeAdapter(Config).validate_python(conf)
