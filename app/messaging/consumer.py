import logging

from typing import TYPE_CHECKING

import psycopg2

from cosmos_message_lib.consumer import AbstractMessageConsumer
from cosmos_message_lib.schemas import ActivitySchema
from psycopg2.extras import Json

if TYPE_CHECKING:
    from kombu import Connection, Exchange
    from kombu.message import Message
    from psycopg2.pool import SimpleConnectionPool

logger = logging.getLogger(__name__)

psycopg2.extensions.register_adapter(dict, Json)


class ActivityConsumer(AbstractMessageConsumer):
    def __init__(
        self,
        rmq_conn: "Connection",
        exchange: "Exchange",
        pg_conn_pool: "SimpleConnectionPool",
        *,
        queue_name: str,
        routing_key: str,
    ):
        self.pg_conn_pool = pg_conn_pool
        super().__init__(rmq_conn, exchange, queue_name=queue_name, routing_key=routing_key, use_deadletter=True)

    def on_message(self, body: dict, message: "Message") -> None:
        try:
            activity = ActivitySchema(**body)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Could not consume message %s\nBody:\n%s", message, body)
            message.reject()
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
                except psycopg2.Error:
                    logger.exception("Problem when persiting data. Requeuing...")
                    message.requeue()
                finally:
                    self.pg_conn_pool.putconn(conn)

            message.ack()
