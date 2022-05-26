# Hubble

BPL activities repository and messaging

## Configuration

- create a `.env` file in the root directory

Example:

```shell
SQLALCHEMY_DATABASE_URI=postgresql://postgres:postgres@localhost:5432/hubble
SQL_DEBUG=False
USE_NULL_POOL=True
RABBIT_URI='amqp://guest:guest@localhost:5672//'
```

- `pipenv install --dev`
