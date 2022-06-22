import logging
import sys

from logging.config import dictConfig

from environs import Env

env = Env()
env.read_env()

DATABASE_URI = env("DATABASE_URI").format(env("DATABASE_NAME", "hubble"))
DATABASE_URI = f"{DATABASE_URI}_test" if any("pytest" in sv for sv in sys.argv) else DATABASE_URI
SENTRY_DSN = env("SENTRY_DSN", None)
SENTRY_ENV = env("SENTRY_ENV", None)
SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE", 0.0)

SQL_DEBUG = env.bool("SQL_DEBUG", False)
RABBIT_DSN = env("RABBIT_DSN")
ROOT_LOG_LEVEL = env.log_level("ROOT_LOG_LEVEL", "INFO")
AMQP_LOG_LEVEL = env.log_level("AMQP_LOG_LEVEL", "INFO")
LOG_FORMATTER = env("LOG_FORMATTER", "brief")

MESSAGE_QUEUE_NAME = env("MESSAGE_QUEUE_NAME", "hubble-activities")
MESSAGE_EXCHANGE = env("MESSAGE_EXCHANGE", "hubble-activities")
MESSAGE_ROUTING_KEY = env("MESSAGE_ROUTING_KEY", "activity.#")

dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "brief": {"format": "%(levelname)s:     %(asctime)s - %(message)s"},
            "console": {"()": "app.reporting.ConsoleFormatter"},
            "detailed": {"()": "app.reporting.ConsoleFormatter"},
            "json": {"()": "app.reporting.JSONFormatter"},
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
