# Hubble

BPL activities repository and messaging

## Development setup

- `$ poetry install`
- `postgres=# CREATE DATABASE hubble;`
- `$ poetry run alembic upgrade head`
- create a `.env` file in the root directory

Example:

```shell
DATABASE_URI=postgresql://postgres:postgres@localhost:5432/hubble
SQL_DEBUG=False
RABBIT_DSN='amqp://guest:guest@localhost:5672//'
ROOT_LOG_LEVEL=DEBUG
LOG_FORMATTER=json
REDIS_URL=redis://localhost:6379/0
```

- `$ poetry run python -m hubble.cli activity-consumer`
