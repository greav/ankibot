from dataclasses import dataclass

from omegaconf import OmegaConf
from pydantic import TypeAdapter

from ankibot.infra.anki.authenticator import AnkiWebAuthenticatorConfig
from ankibot.infra.anki.card_gateway import AnkiWebCardGatewayConfig
from ankibot.infra.logger import LoggerConfig


@dataclass(frozen=True, kw_only=True)
class BotConfig:
    token: str


@dataclass(frozen=True, kw_only=True)
class Config:
    bot: BotConfig
    logger: LoggerConfig
    anki_web: AnkiWebAuthenticatorConfig
    anki_card_gateway: AnkiWebCardGatewayConfig


def load_config(path: str) -> Config:
    conf = OmegaConf.to_container(OmegaConf.load(path), resolve=True)

    return TypeAdapter(Config).validate_python(conf)
