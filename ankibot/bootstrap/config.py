from dataclasses import dataclass

from omegaconf import OmegaConf
from pydantic import TypeAdapter

from ankibot.application.english_card_generation.models import CardTemplate
from ankibot.infra.ai.openai_card_generator import OpenAICardGeneratorConfig
from ankibot.infra.anki.httpx_anki_gateway import AnkiWebGatewayConfig
from ankibot.infra.logger import LoggerConfig


@dataclass
class BotConfig:
    token: str


@dataclass
class Config:
    bot: BotConfig
    logger: LoggerConfig
    openai: OpenAICardGeneratorConfig
    ankiweb: AnkiWebGatewayConfig
    card_template: CardTemplate


def load_config(path: str) -> Config:
    conf = OmegaConf.to_container(OmegaConf.load(path), resolve=True)

    return TypeAdapter(Config).validate_python(conf)
