from dataclasses import dataclass
from typing import List, Optional

from omegaconf import OmegaConf
from pydantic import BaseModel, TypeAdapter, field_validator

from .infra.logger import LoggerConfig


class BotConfig(BaseModel):
    token: str
    admin_user_ids: Optional[List[int]] = []

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admin_user_ids(cls, v):
        """Parse admin user IDs from various formats."""
        if v is None or v == "[]" or v == "":
            return []
        if isinstance(v, str):
            # Parse string like "[123,456]" or "123,456"
            import ast

            try:
                if v.startswith("[") and v.endswith("]"):
                    return ast.literal_eval(v)
                else:
                    return [int(x.strip()) for x in v.split(",") if x.strip()]
            except (ValueError, SyntaxError):
                return []
        if isinstance(v, list):
            return [int(x) for x in v if str(x).isdigit()]
        return []


@dataclass
class AnkiConfig:
    username: str
    password: str


@dataclass
class OpenAIConfig:
    api_key: str
    model: str
    max_cards: int = 10


@dataclass
class Config:
    bot: BotConfig
    logger: LoggerConfig
    anki: AnkiConfig
    openai: OpenAIConfig


def load_config(path: str) -> Config:
    conf = OmegaConf.to_container(OmegaConf.load(path), resolve=True)

    return TypeAdapter(Config).validate_python(conf)
