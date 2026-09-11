import contextvars
import logging
from dataclasses import dataclass
from typing import override

request_id_var = contextvars.ContextVar("request_id", default="NA")

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class RequestFormatter(logging.Formatter):
    @override
    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get()

        return super().format(record)


@dataclass(frozen=True, kw_only=True)
class LoggerConfig:
    level: str
    fmt: str


def configure_root_logger(config: LoggerConfig) -> logging.Logger:
    stream_handler = logging.StreamHandler()
    formatter = RequestFormatter(config.fmt)
    stream_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(stream_handler)
    root_logger.setLevel(LOG_LEVELS.get(config.level, logging.WARNING))
    # httpx logs every request's full URL at INFO, and AnkiWeb's token exchange carries the login
    # ticket in a query parameter. The adapters report their own outcomes, so nothing is lost.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return root_logger
