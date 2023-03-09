import logging

from typing import TYPE_CHECKING

import psycopg

from cosmos_message_lib.consumer import AbstractMessageConsumer
from cosmos_message_lib.schemas import ActivitySchema
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from hubble import settings

if TYPE_CHECKING:
    from kombu import Connection, Exchange
    from kombu.message import Message
    from psycopg.connection import Connection as PGConn

logger = logging.getLogger(__name__)


class ActivityConsumer(AbstractMessageConsumer):
    def __init__(
        self,
        rmq_conn: "Connection",
        exchange: "Exchange",
        *,
        queue_name: str,
        routing_key: str,
    ) -> None:
        self._pg_conn_pool: ConnectionPool | None = None
        self._pg_pooling: bool = settings.PG_CONNECTION_POOLING
        logger.info(f"Connection pooling: {self._pg_pooling}")
        if self._pg_pooling:
            self._pg_conn_pool = ConnectionPool(settings.PSYCOPG_URI, min_size=1, max_size=10)

        super().__init__(rmq_conn, exchange, queue_name=queue_name, routing_key=routing_key, use_deadletter=True)

    @staticmethod
    def prepare_for_insert(val: ActivitySchema) -> dict:
        payload = val.dict()
        payload["data"] = Jsonb(payload["data"])
        return payload

    def get_pg_conn(self) -> "PGConn":
        if self._pg_conn_pool:
            return self._pg_conn_pool.getconn()

        return psycopg.connect(settings.PSYCOPG_URI)

    def on_message(self, body: dict | list[dict], message: "Message") -> None:
        activities: list[ActivitySchema] = []
        try:
            if isinstance(body, list):
                activities = [self.prepare_for_insert(ActivitySchema(**data)) for data in body]
            else:
                activities = [self.prepare_for_insert(ActivitySchema(**body))]
        except Exception:
            logger.exception("Could not consume message %s\nBody:\n%s", message, body)
            message.reject()
        else:
            conn = self.get_pg_conn()
            try:
                with conn.cursor() as cur:
                    cur.executemany(
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
                        activities,
                    )

            except psycopg.Error as ex:
                logger.exception("Problem when persiting data. Requeuing...", exc_info=ex)
                conn.rollback()
                message.requeue()
            else:
                conn.commit()
                message.ack()
                logger.debug("Persisted %s activity objects", len(activities))
            finally:
                if self._pg_conn_pool:
                    self._pg_conn_pool.putconn(conn)
                else:
                    conn.close()
