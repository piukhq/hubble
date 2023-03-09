from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

from psycopg import connect, sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from sqlalchemy import create_engine

from hubble.db.models import Base
from hubble.settings import PSYCOPG_URI, SQLALCHEMY_URI

if TYPE_CHECKING:
    from psycopg import Connection, Cursor
    from psycopg.rows import DictRow
    from sqlalchemy.engine import Engine


@pytest.fixture(scope="session", autouse=True)
def setup_db() -> Generator:
    conn_args = conninfo_to_dict(PSYCOPG_URI)
    db_name = conn_args.pop("dbname")
    conn_args.update({"dbname": "postgres"})
    conn = connect(make_conninfo(**conn_args), autocommit=True)
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
    return create_engine(SQLALCHEMY_URI)


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
def psycopg_connection() -> Generator["Connection[DictRow]", None, None]:
    conn = connect(PSYCOPG_URI, row_factory=dict_row)
    yield conn
    conn.commit()
    conn.close()


@pytest.fixture(scope="function")
def db_dict_cursor(psycopg_connection: "Connection[DictRow]") -> Generator["Cursor[DictRow]", None, None]:
    cursor = psycopg_connection.cursor()
    yield cursor
    cursor.close()
