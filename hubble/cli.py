import logging

import sentry_sdk
import typer

from cosmos_message_lib.connection import get_connection_and_exchange

from hubble import settings
from hubble.messaging.consumer import ActivityConsumer
from hubble.version import __version__

cli = typer.Typer()
logger = logging.getLogger(__name__)

if settings.SENTRY_DSN:  # pragma: no cover
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENV,
        release=__version__,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )


@cli.command()
def activity_consumer() -> None:
    rmq_conn, exchange = get_connection_and_exchange(
        rabbitmq_dsn=settings.RABBIT_DSN, message_exchange_name=settings.MESSAGE_EXCHANGE
    )
    ActivityConsumer(
        rmq_conn,
        exchange,
        queue_name=settings.MESSAGE_QUEUE_NAME,
        routing_key=settings.MESSAGE_ROUTING_KEY,
    ).run()


@cli.callback()
def callback() -> None:
    """
    hubble command line interface
    """


if __name__ == "__main__":
    cli()