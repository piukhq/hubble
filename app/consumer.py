from kombu import Connection, Exchange, Queue
from kombu.mixins import ConsumerMixin

from app import settings


class ActivityConsumer(ConsumerMixin):
    exchange = Exchange(settings.MESSAGE_EXCHANGE, type="topic", durable=True)
    queue = Queue(
        settings.MESSAGE_QUEUE_NAME,
        durable=True,
        exchange=exchange,
        routing_key=settings.MESSAGE_ROUTING_KEY,
    )

    def __init__(self, conn: Connection):
        self.connection = conn

    def get_consumers(self, Consumer, channel) -> list:
        return [
            Consumer(queues=[self.queue], callbacks=[self.on_message], accept=["json"]),
        ]

    def on_message(self, body, message) -> None:  # pylint: disable=no-self-use
        print("RECEIVED MESSAGE: {0!r}".format(body))
        message.ack()


if __name__ == "__main__":
    connection = Connection(settings.RABBIT_URI)
    ActivityConsumer(connection).run()
