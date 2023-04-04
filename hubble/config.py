import logging
import sys

from logging.config import dictConfig
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseSettings, validator
from redis import Redis
from retry_tasks_lib.settings import load_settings

LogLevels = Literal["CRITICAL", "FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "NOTSET"]


class Settings(BaseSettings):
    PROJECT_NAME: str = "hubble"
    TESTING: bool = False

    @validator("TESTING", always=True, pre=False)
    @classmethod
    def is_test(cls, v: bool) -> bool:
        return True if any("pytest" in arg for arg in sys.argv) else v

    # these values will be calculated automatically from DATABASE_URI, they must be placed before DATABASE_URI
    PSYCOPG_URI: str = None  # type: ignore [assignment]
    SQLALCHEMY_URI: str = None  # type: ignore [assignment]
    # ------------------------------------------------------------------------------------------------------ #

    DATABASE_NAME: str = "hubble"
    DATABASE_URI: str

    @validator("DATABASE_URI", always=True, pre=False)
    @classmethod
    def process_db_uris(cls, v: str, values: dict) -> str:
        db_uri = v.format(values["DATABASE_NAME"])

        if values["TESTING"]:
            current_value = urlparse(db_uri)
            current_value = current_value._replace(path=f"{current_value.path}_test")
            db_uri = current_value.geturl()

        if "+psycopg" in db_uri:
            values["PSYCOPG_URI"] = db_uri.replace("+psycopg", "")
            values["SQLALCHEMY_URI"] = db_uri
        else:
            values["PSYCOPG_URI"] = db_uri
            base, info = db_uri.split("://")
            values["SQLALCHEMY_URI"] = f"{base}+psycopg://{info}"

        return db_uri

    PG_CONNECTION_POOLING: bool = True

    SENTRY_DSN: str | None = None
    SENTRY_ENV: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    SQL_DEBUG: bool = False
    RABBIT_DSN: str
    ROOT_LOG_LEVEL: LogLevels = "INFO"
    AMQP_LOG_LEVEL: LogLevels = "INFO"
    LOG_FORMATTER: Literal["brief", "console", "detailed" "json"] = "brief"

    MESSAGE_QUEUE_NAME: str = "hubble-activities"
    MESSAGE_EXCHANGE: str = "hubble-activities"
    MESSAGE_ROUTING_KEY: str = "activity.#"

    USE_NULL_POOL: bool = False
    DB_CONNECTION_RETRY_TIMES: int = 3
    DEFAULT_FAILURE_TTL: int = 60 * 60 * 24 * 7  # 1 week

    REDIS_URL: str

    @validator("REDIS_URL", always=True, pre=False)
    @classmethod
    def assemble_redis_url(cls, v: str, values: dict) -> str:
        if values["TESTING"]:
            base_url, db_n = v.rsplit("/", 1)
            return f"{base_url}/{int(db_n) + 1}"
        return v

    TASK_QUEUE_PREFIX: str = "hubble:"
    TASK_QUEUES: list[str] = None  # type: ignore [assignment]

    @validator("TASK_QUEUES")
    @classmethod
    def task_queues(cls, v: list[str] | None, values: dict) -> list[str]:
        return v or [values["TASK_QUEUE_PREFIX"] + name for name in ("high", "default", "low")]

    ANONYMISE_ACTIVITIES_TASK_NAME: str = "anonymise-activities"

    ACTIVATE_TASKS_METRICS: bool = True
    PROMETHEUS_HTTP_SERVER_PORT: int = 9100

    REDIS_KEY_PREFIX = "hubble:"
    TASK_CLEANUP_SCHEDULE: str = "0 1 * * *"
    TASK_DATA_RETENTION_DAYS: int = 180

    class Config:
        case_sensitive = True
        # env var settings priority ie priority 1 will override priority 2:
        # 1 - env vars already loaded (ie the one passed in by kubernetes)
        # 2 - env vars read from .env file
        # 3 - values assigned directly in the Settings class
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

load_settings(settings)

redis = Redis.from_url(
    settings.REDIS_URL,
    socket_connect_timeout=3,
    socket_keepalive=True,
    retry_on_timeout=False,
    decode_responses=True,
)

redis_raw = Redis.from_url(
    settings.REDIS_URL,
    socket_connect_timeout=3,
    socket_keepalive=True,
    retry_on_timeout=False,
)

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
                "formatter": settings.LOG_FORMATTER,
            },
            "stdout": {
                "level": logging.NOTSET,
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": settings.LOG_FORMATTER,
            },
        },
        "loggers": {
            "root": {
                "level": settings.ROOT_LOG_LEVEL,
                "handlers": ["stdout"],
            },
            "alembic": {
                "level": settings.ROOT_LOG_LEVEL,
                "handlers": ["stderr"],
                "propagate": False,
            },
            "amqp": {
                "level": settings.AMQP_LOG_LEVEL,
                "handlers": ["stdout"],
            },
        },
    }
)
