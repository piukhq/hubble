import logging

from typing import TYPE_CHECKING, Any, Generator, Type

import psycopg2

from amqp import Channel
from cosmos_message_lib.schemas import ActivitySchema
from kombu import Connection, Queue
from kombu.mixins import ConsumerMixin
from psycopg2.extras import Json
from pydantic import ValidationError

from app import settings

if TYPE_CHECKING:
    from kombu import Consumer as ConsumerCls
    from kombu import Exchange
    from kombu.message import Message
    from psycopg2.pool import SimpleConnectionPool

logger = logging.getLogger(__name__)

psycopg2.extensions.register_adapter(dict, Json)


class ActivityConsumer(ConsumerMixin):
    def __init__(
        self,
        rmq_conn: Connection,
        exchange: "Exchange",
        pg_conn_pool: "SimpleConnectionPool",
        message_queue_name: str = settings.MESSAGE_QUEUE_NAME,
    ):
        self.connection = rmq_conn
        channel = rmq_conn.channel()
        self.pg_conn_pool = pg_conn_pool
        exchange = exchange(channel)
        exchange.declare()
        queue = Queue(
            message_queue_name,
            durable=True,
            exchange=exchange,
            routing_key=settings.MESSAGE_ROUTING_KEY,
        )
        self.queue = queue(channel)
        self.queue.declare()

    def get_consumers(self, Consumer: Type["ConsumerCls"], channel: Channel) -> list:
        return [
            Consumer(queues=[self.queue], callbacks=[self.on_message], accept=["json"]),
        ]

    def consume(self, *args: Any, **kwargs: Any) -> Generator:
        consume = self.connection.ensure(self.connection, super().consume)
        return consume(*args, **kwargs)

    def on_message(self, body: dict, message: "Message") -> None:
        try:
            activity = ActivitySchema(**body)
        except ValidationError:
            logger.exception("Could not consume message %s\nBody:\n%s", message, body)
        else:
            with self.pg_conn_pool.getconn() as conn:
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO activity "
                        "VALUES "
                        "("
                        "%(id)s, "
                        "%(type)s, "
                        "%(datetime)s, "
                        "%(underlying_datetime)s, "
                        "%(summary)s, "
                        "%(reasons)s, "
                        "%(activity_identifier)s, "
                        "%(user_id)s, "
                        "%(associated_value)s, "
                        "%(retailer)s, "
                        "%(campaigns)s, "
                        "%(data)s"
                        ");",
                        activity.dict(),
                    )
                    conn.commit()
                    logger.debug("Persisted %s activity with id %s", activity.type, activity.id)
                finally:
                    self.pg_conn_pool.putconn(conn)

            message.ack()
