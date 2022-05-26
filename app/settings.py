from environs import Env

env = Env()
env.read_env()

SQLALCHEMY_DATABASE_URI = env("SQLALCHEMY_DATABASE_URI")
SQL_DEBUG = env.bool("SQL_DEBUG", False)
USE_NULL_POOL = env.bool("USE_NULL_POOL", False)
RABBIT_URI = env("RABBIT_URI")
MESSAGE_QUEUE_NAME = env("MESSAGE_QUEUE_NAME", "activity")
MESSAGE_EXCHANGE = env("MESSAGE_EXCHANGE", "hubble-activities")
MESSAGE_ROUTING_KEY = env("MESSAGE_ROUTING_KEY", "activity.#")
