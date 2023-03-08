from collections.abc import Generator
from typing import TYPE_CHECKING

import psycopg2
import pytest

from psycopg2 import connect, extensions, sql
from psycopg2.extensions import make_dsn, parse_dsn
from sqlalchemy.engine import create_engine

from hubble.db.models import Base
from hubble.settings import DATABASE_URI

if TYPE_CHECKING:
    from psycopg2 import connection, cursor
    from sqlalchemy.engine import Engine


@pytest.fixture(scope="session", autouse=True)
def setup_db() -> Generator:
    conn_args = parse_dsn(DATABASE_URI)
    db_name = conn_args.pop("dbname")
    conn_args.update({"dbname": "postgres"})
    conn = connect(make_dsn(**conn_args))
    conn.set_isolation_level(extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    if not db_name.endswith("_test"):
        raise ValueError(f"Unsafe attempt to recreate database: {db_name}")

    cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(db_name)))
    cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))

    yield

    cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(db_name)))
    cursor.close()
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def db_engine() -> "Engine":
    return create_engine(DATABASE_URI)


@pytest.fixture(scope="function", autouse=True)
def setup_tables(db_engine: "Engine") -> Generator:
    """
    autouse set to True so will be run before each test function, to set up tables
    and tear them down after each test runs
    """
    Base.metadata.create_all(bind=db_engine)
    yield
    Base.metadata.drop_all(bind=db_engine)


@pytest.fixture(scope="function")
def psycopg2_connection() -> Generator:
    conn = connect(DATABASE_URI)
    yield conn
    conn.commit()
    conn.close()


@pytest.fixture(scope="function")
def db_dict_cursor(psycopg2_connection: "connection") -> "cursor":
    cursor = psycopg2_connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    yield cursor
    cursor.close()
