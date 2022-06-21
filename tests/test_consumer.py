import uuid

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Generator

import pytest

from cosmos_message_lib.connection import get_connection_and_exchange
from cosmos_message_lib.enums import ActivityType
from cosmos_message_lib.producer import send_message
from cosmos_message_lib.schemas import ActivitySchema
from kombu import BrokerConnection, Exchange
from psycopg2 import sql
from psycopg2.pool import SimpleConnectionPool

from app import settings
from app.messaging.consumer import ActivityConsumer

if TYPE_CHECKING:
    from psycopg2 import cursor


@pytest.fixture(name="connection_and_exchange", scope="module")
def fixture_connection_and_exchange() -> Generator:
    rmq_conn, exchange = get_connection_and_exchange(
        rabbitmq_dsn=settings.RABBIT_DSN, message_exchange_name=f"{settings.MESSAGE_EXCHANGE}-test"
    )
    channel = rmq_conn.channel()
    exchange = exchange.bind(channel=channel)
    yield rmq_conn, exchange
    exchange.delete()
    rmq_conn.release()


@pytest.fixture
def pg_conn_pool() -> SimpleConnectionPool:
    return SimpleConnectionPool(dsn=settings.DATABASE_URI, minconn=1, maxconn=5)


@pytest.fixture(name="consumer")
def fixture_consumer(
    connection_and_exchange: tuple[BrokerConnection, Exchange], pg_conn_pool: SimpleConnectionPool
) -> Generator:
    rmq_conn, exchange = connection_and_exchange
    activity_consumer = ActivityConsumer(
        rmq_conn,
        exchange,
        pg_conn_pool,
        queue_name=f"{settings.MESSAGE_QUEUE_NAME}-test",
        routing_key=settings.MESSAGE_ROUTING_KEY,
    )
    yield activity_consumer
    channel = rmq_conn.channel()
    activity_consumer.deadletter_queue(channel).delete()
    activity_consumer.deadletter_exchange(channel).delete()
    activity_consumer.queue.delete()


def test_consumer(
    consumer: ActivityConsumer,
    connection_and_exchange: tuple[BrokerConnection, Exchange],
    db_dict_cursor: "cursor",
) -> None:
    rmq_conn, exchange = connection_and_exchange

    now = datetime.now(tz=timezone.utc)
    yesterday = now - timedelta(days=1)
    activity_identifier, user_id = str(uuid.uuid4()), str(uuid.uuid4())
    data = ActivitySchema(
        **{
            "type": ActivityType.TX_HISTORY,
            "datetime": now,
            "underlying_datetime": yesterday,
            "summary": "Headline!",
            "reasons": ["a reason", "another reason"],
            "activity_identifier": activity_identifier,
            "user_id": user_id,
            "associated_value": "42",
            "retailer": "asos",
            "campaigns": ["ASOS_EXTRA"],
            "data": {
                "some": "data",
                "such": "wow",
            },
        }
    ).dict()

    send_message(rmq_conn, exchange, data, routing_key="activity.random")
    for _ in consumer.consume(limit=1):
        pass

    db_dict_cursor.execute(sql.SQL("SELECT count(1) FROM activity;"))
    res = db_dict_cursor.fetchone()
    assert res == [1]

    db_dict_cursor.execute(sql.SQL("SELECT * FROM activity LIMIT 1;"))
    res = db_dict_cursor.fetchone()
    assert res["type"] == ActivityType.TX_HISTORY.name
    assert res["datetime"].replace(tzinfo=timezone.utc) == now  # Note that timestamps are a naive
    assert res["activity_identifier"] == activity_identifier
    assert res["associated_value"] == "42"
    assert res["data"] == {"some": "data", "such": "wow"}
