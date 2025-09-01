import contextvars
import logging
from dataclasses import dataclass

request_id_var = contextvars.ContextVar("request_id", default="NA")

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class RequestFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get()

        return super().format(record)


@dataclass
class LoggerConfig:
    level: str = "INFO"
    fmt: str = DEFAULT_FORMAT


def configure_root_logger(config: LoggerConfig) -> logging.Logger:
    stream_handler = logging.StreamHandler()
    formatter = RequestFormatter(config.fmt)
    stream_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(stream_handler)
    root_logger.setLevel(LOG_LEVELS.get(config.level, logging.WARNING))
    return root_logger
