import uuid

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Generator
from unittest import mock

import psycopg2
import pytest

from cosmos_message_lib import ActivitySchema, get_connection_and_exchange, send_message
from kombu import Connection, Exchange, Message
from psycopg2 import sql
from psycopg2.pool import SimpleConnectionPool

from hubble import settings
from hubble.messaging.consumer import ActivityConsumer

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
    connection_and_exchange: tuple[Connection, Exchange], pg_conn_pool: SimpleConnectionPool
) -> Generator:
    rmq_conn, exchange = connection_and_exchange
    activity_consumer = ActivityConsumer(
        rmq_conn,
        exchange,
        queue_name=f"{settings.MESSAGE_QUEUE_NAME}-test",
        routing_key=settings.MESSAGE_ROUTING_KEY,
    )
    yield activity_consumer
    channel = rmq_conn.channel()
    activity_consumer.deadletter_queue(channel).delete()
    activity_consumer.deadletter_exchange(channel).delete()
    activity_consumer.queue.delete()


def test_consumer_single(
    consumer: ActivityConsumer,
    connection_and_exchange: tuple[Connection, Exchange],
    db_dict_cursor: "cursor",
) -> None:
    rmq_conn, exchange = connection_and_exchange
    activity_type = "TX_HISTORY"
    now = datetime.now(tz=timezone.utc)
    yesterday = now - timedelta(days=1)
    activity_identifier, user_id = str(uuid.uuid4()), str(uuid.uuid4())
    data = ActivitySchema(
        **{
            "type": activity_type,
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
    assert res["type"] == activity_type
    assert res["datetime"].replace(tzinfo=timezone.utc) == now  # Note that timestamps are a naive
    assert res["activity_identifier"] == activity_identifier
    assert res["associated_value"] == "42"
    assert res["data"] == {"some": "data", "such": "wow"}


def test_consumer_multiple_list(
    consumer: ActivityConsumer,
    connection_and_exchange: tuple[Connection, Exchange],
    db_dict_cursor: "cursor",
) -> None:
    rmq_conn, exchange = connection_and_exchange
    activity_type = "TX_HISTORY"
    now = datetime.now(tz=timezone.utc)
    yesterday = now - timedelta(days=1)
    activity_identifier, user_id = str(uuid.uuid4()), str(uuid.uuid4())
    data = [
        ActivitySchema(
            **{
                "type": activity_type,
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
        for _ in range(10)
    ]

    send_message(rmq_conn, exchange, data, routing_key="activity.random")
    for _ in consumer.consume(limit=1):
        pass

    db_dict_cursor.execute(sql.SQL("SELECT count(1) FROM activity;"))
    res = db_dict_cursor.fetchone()
    assert res == [10]


def test_consumer_bad_data_rejected() -> None:
    mock_pg_conn_pool = mock.MagicMock()
    mock_conn = mock.MagicMock()
    mock_pg_conn_pool.getconn.return_value = mock_conn
    mock_rabbit_conn = mock.MagicMock()
    mock_rabbit_exchange = mock.MagicMock()
    consumer = ActivityConsumer(
        mock_rabbit_conn, mock_rabbit_exchange, queue_name="queue-name", routing_key="routing-key"
    )
    mock_message = mock.MagicMock(spec=Message)
    consumer.on_message({"some": "bad data"}, mock_message)
    mock_message.reject.assert_called_once()


@mock.patch("hubble.messaging.consumer.execute_batch", side_effect=psycopg2.Error("Boom"))
def test_consumer_db_problem_requeued(mock_execute_batch: mock.MagicMock) -> None:  # pylint: disable=unused-argument
    mock_pg_conn_pool = mock.MagicMock()
    mock_conn = mock.MagicMock()
    mock_pg_conn_pool.getconn.return_value = mock_conn
    mock_cursor = mock.MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_rabbit_conn = mock.MagicMock()
    mock_rabbit_exchange = mock.MagicMock()
    consumer = ActivityConsumer(
        mock_rabbit_conn, mock_rabbit_exchange, queue_name="queue-name", routing_key="routing-key"
    )
    mock.patch.object(consumer, "pg_conn_pool", mock_pg_conn_pool)

    consumer._pg_conn_pool = mock_pg_conn_pool  # pylint: disable=protected-access
    mock_message = mock.MagicMock(spec=Message)
    data = ActivitySchema(
        **{
            "type": "TX_HISTORY",
            "datetime": datetime.now(tz=timezone.utc),
            "underlying_datetime": datetime.now(tz=timezone.utc),
            "summary": "Headline!",
            "reasons": ["a reason", "another reason"],
            "activity_identifier": "a_id",
            "user_id": str(uuid.uuid4()),
            "associated_value": "42",
            "retailer": "asos",
            "campaigns": ["ASOS_EXTRA"],
            "data": {
                "some": "data",
                "such": "wow",
            },
        }
    ).dict()
    consumer.on_message(data, mock_message)
    mock_message.requeue.assert_called_once()
