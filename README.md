# Hubble

BPL activities repository and messaging

## Development setup

- `$ pipenv install --dev`
- `postgres=# CREATE DATABASE hubble;`
- `$ pipenv run alembic upgrade head`
- create a `.env` file in the root directory

Example:

```shell
DATABASE_URI=postgresql://postgres:postgres@localhost:5432/hubble
SQL_DEBUG=False
RABBIT_URI='amqp://guest:guest@localhost:5672//'
ROOT_LOG_LEVEL=DEBUG
LOG_FORMATTER=json
```

- `$ pipenv run python -m app.cli activity-consumer`
