import logging

import typer

from cosmos_message_lib.connection import get_connection_and_exchange
from psycopg2.pool import SimpleConnectionPool

from app import settings
from app.messaging.consumer import ActivityConsumer

cli = typer.Typer()
logger = logging.getLogger(__name__)


@cli.command()
def activity_consumer() -> None:

    rmq_conn, exchange = get_connection_and_exchange(
        rabbitmq_uri=settings.RABBIT_URI, message_exchange_name=settings.MESSAGE_EXCHANGE
    )
    pg_conn_pool = SimpleConnectionPool(dsn=settings.DATABASE_URI, minconn=1, maxconn=5)
    ActivityConsumer(rmq_conn, exchange, pg_conn_pool).run()


@cli.callback()
def callback() -> None:
    """
    hubble command line interface
    """


if __name__ == "__main__":
    cli()
