import logging

from typing import TYPE_CHECKING, Any

import psycopg2

from cosmos_message_lib.consumer import AbstractMessageConsumer
from cosmos_message_lib.schemas import ActivitySchema
from psycopg2.extras import Json
from psycopg2.pool import SimpleConnectionPool

from app import settings

if TYPE_CHECKING:
    from kombu import Connection, Exchange
    from kombu.message import Message

logger = logging.getLogger(__name__)

psycopg2.extensions.register_adapter(dict, Json)


class ActivityConsumer(AbstractMessageConsumer):
    def __init__(
        self,
        rmq_conn: "Connection",
        exchange: "Exchange",
        *,
        queue_name: str,
        routing_key: str,
    ):
        self._pg_pooling: bool = settings.PG_CONNECTION_POOLING
        logger.info(f"Connection pooling: {self._pg_pooling}")
        if self._pg_pooling:
            self._pg_conn_pool = SimpleConnectionPool(dsn=settings.DATABASE_URI, minconn=1, maxconn=10)
        else:
            self._pg_conn_pool = None

        super().__init__(rmq_conn, exchange, queue_name=queue_name, routing_key=routing_key, use_deadletter=True)

    def get_pg_conn(self) -> Any:  # no type hinting in psycopg2
        if self._pg_pooling:
            return self._pg_conn_pool.getconn()
        return psycopg2.connect(settings.DATABASE_URI)

    def on_message(self, body: dict, message: "Message") -> None:
        try:
            activity = ActivitySchema(**body)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Could not consume message %s\nBody:\n%s", message, body)
            message.reject()
        else:
            conn = self.get_pg_conn()
            try:
                with conn.cursor() as cur:
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
            except psycopg2.Error as ex:
                logger.exception("Problem when persiting data. Requeuing...", exc_info=ex)
                conn.rollback()
                message.requeue()
            finally:
                if self._pg_pooling:
                    self._pg_conn_pool.putconn(conn)
                else:
                    conn.close()

            message.ack()
