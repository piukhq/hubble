import logging
import sys

from logging.config import dictConfig
from urllib.parse import urlparse

from decouple import Choices, config

ALLOWED_LOG_LEVELS = Choices(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"])

DATABASE_NAME = config("DATABASE_NAME", "hubble")
DATABASE_URI = config("DATABASE_URI").format(DATABASE_NAME)

command = sys.argv[0]
args = sys.argv[1:] if len(sys.argv) > 1 else []

if "pytest" in command or any("test" in arg for arg in args):
    current_value = urlparse(DATABASE_URI)
    current_value = current_value._replace(path=f"{current_value.path}_test")
    DATABASE_URI = current_value.geturl()

if "+psycopg" in DATABASE_URI:
    PSYCOPG_URI = DATABASE_URI.replace("+psycopg", "")
    SQLALCHEMY_URI = DATABASE_URI
else:
    PSYCOPG_URI = DATABASE_URI
    base, info = DATABASE_URI.split("://")
    SQLALCHEMY_URI = f"{base}+psycopg://{info}"

PG_CONNECTION_POOLING = config("PG_CONNECTION_POOLING", True, cast=bool)

SENTRY_DSN = config("SENTRY_DSN", None)
SENTRY_ENV = config("SENTRY_ENV", None)
SENTRY_TRACES_SAMPLE_RATE = config("SENTRY_TRACES_SAMPLE_RATE", 0.0, cast=float)

SQL_DEBUG = config("SQL_DEBUG", False, cast=bool)
RABBIT_DSN = config("RABBIT_DSN")
ROOT_LOG_LEVEL: str = config("ROOT_LOG_LEVEL", default="INFO", cast=ALLOWED_LOG_LEVELS)
AMQP_LOG_LEVEL: str = config("AMQP_LOG_LEVEL", default="INFO", cast=ALLOWED_LOG_LEVELS)
LOG_FORMATTER: str = config("LOG_FORMATTER", default="brief", cast=Choices(["brief", "console", "detailed" "json"]))

MESSAGE_QUEUE_NAME = config("MESSAGE_QUEUE_NAME", "hubble-activities")
MESSAGE_EXCHANGE = config("MESSAGE_EXCHANGE", "hubble-activities")
MESSAGE_ROUTING_KEY = config("MESSAGE_ROUTING_KEY", "activity.#")

dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "brief": {"format": "%(levelname)s:     %(asctime)s - %(message)s"},
            "console": {"()": "hubble.reporting.ConsoleFormatter"},
            "detailed": {"()": "hubble.reporting.ConsoleFormatter"},
            "json": {"()": "hubble.reporting.JSONFormatter"},
        },
        "handlers": {
            "stderr": {
                "level": logging.NOTSET,
                "class": "logging.StreamHandler",
                "stream": sys.stderr,
                "formatter": LOG_FORMATTER,
            },
            "stdout": {
                "level": logging.NOTSET,
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": LOG_FORMATTER,
            },
        },
        "loggers": {
            "root": {
                "level": ROOT_LOG_LEVEL,
                "handlers": ["stdout"],
            },
            "alembic": {
                "level": ROOT_LOG_LEVEL,
                "handlers": ["stderr"],
                "propagate": False,
            },
            "amqp": {
                "level": AMQP_LOG_LEVEL,
                "handlers": ["stdout"],
            },
        },
    }
)
