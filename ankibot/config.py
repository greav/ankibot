from dataclasses import dataclass

from omegaconf import OmegaConf
from pydantic import TypeAdapter

from .infra.logger import LoggerConfig


@dataclass
class BotConfig:
    token: str


@dataclass
class AnkiConfig:
    username: str
    password: str


@dataclass
class Config:
    bot: BotConfig
    logger: LoggerConfig
    anki: AnkiConfig


def load_config(path: str) -> Config:
    conf = OmegaConf.to_container(OmegaConf.load(path), resolve=True)

    return TypeAdapter(Config).validate_python(conf)
