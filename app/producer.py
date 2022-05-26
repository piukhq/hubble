import random
import uuid

from kombu import Connection, Exchange

from app import settings

exchange = Exchange(settings.MESSAGE_EXCHANGE, type="topic", durable=True, delivery_mode="persistent")

if __name__ == "__main__":
    with Connection(settings.RABBIT_URI) as connection:
        producer = connection.Producer()
        uid_str = str(uuid.uuid4())
        for i in range(5):
            routing_key = random.choice(["activity.random", "activity.vela.tx-processed"])
            producer.publish(
                {uid_str: i, "routing_key": routing_key},  # message to send
                exchange=exchange,  # destination exchange
                routing_key=routing_key,  # destination routing key,
                declare=[exchange],  # make sure exchange is declared,
            )
