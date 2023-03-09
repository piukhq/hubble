from collections.abc import Callable, Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from psycopg import connect, sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from retry_tasks_lib.db.models import RetryTask, TaskType, TaskTypeKey, TaskTypeKeyValue

from hubble.config import settings
from hubble.db.models import Activity, Base
from hubble.db.session import SessionMaker, engine

if TYPE_CHECKING:
    from psycopg import Connection, Cursor
    from psycopg.rows import DictRow
    from sqlalchemy.orm import Session


@pytest.fixture(scope="session", autouse=True)
def setup_db() -> Generator:
    conn_args = conninfo_to_dict(settings.PSYCOPG_URI)
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


@pytest.fixture(scope="function", autouse=True)
def setup_tables() -> Generator:
    """
    autouse set to True so will be run before each test function, to set up tables
    and tear them down after each test runs
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def psycopg_connection() -> Generator["Connection[DictRow]", None, None]:
    conn = connect(settings.PSYCOPG_URI, row_factory=dict_row)
    yield conn
    conn.commit()
    conn.close()


@pytest.fixture(scope="function")
def db_dict_cursor(psycopg_connection: "Connection[DictRow]") -> Generator["Cursor[DictRow]", None, None]:
    cursor = psycopg_connection.cursor()
    yield cursor
    cursor.close()


@pytest.fixture(scope="function", name="db_session")
def sqlalchemy_db_session() -> Generator["Session", None, None]:
    with SessionMaker() as session:
        yield session


@pytest.fixture(scope="function")
def anonymise_activities_task_type(db_session: "Session") -> TaskType:
    tt = TaskType(
        name=settings.ANONYMISE_ACTIVITIES_TASK_NAME,
        path="hubble.tasks.right_to_be_forgotten.anonymise_activities",
        error_handler_path="hubble.tasks.error_handlers.default_handler",
        queue_name="hubble:default",
    )
    db_session.add(tt)
    db_session.flush()
    db_session.bulk_save_objects(
        [
            TaskTypeKey(task_type_id=tt.task_type_id, name=key_name, type=key_type)
            for key_name, key_type in (
                ("retailer_slug", "STRING"),
                ("account_holder_uuid", "STRING"),
                ("account_holder_email", "STRING"),
            )
        ]
    )
    db_session.commit()
    return tt


@pytest.fixture(scope="function")
def anonymise_activities_task(db_session: "Session", anonymise_activities_task_type: TaskType) -> TaskType:

    rt = RetryTask(task_type_id=anonymise_activities_task_type.task_type_id)
    db_session.add(rt)
    db_session.flush()
    key_ids = anonymise_activities_task_type.get_key_ids_by_name()
    db_session.bulk_save_objects(
        [
            TaskTypeKeyValue(
                task_type_key_id=key_ids[key_name],
                value=value,
                retry_task_id=rt.retry_task_id,
            )
            for key_name, value in (
                ("retailer_slug", "test-retailer"),
                ("account_holder_uuid", str(uuid4())),
                ("account_holder_email", "sample@user.email"),
            )
        ]
    )
    db_session.commit()
    return rt


@pytest.fixture(scope="function")
def create_activity(db_session: "Session") -> Callable[..., Activity]:
    payload = {
        "id": str(uuid4()),
        "type": "TEST",
        "datetime": datetime.now(tz=UTC),
        "underlying_datetime": datetime.now(tz=UTC),
        "summary": "sample summary",
        "reasons": ["sample reason"],
        "activity_identifier": "TST_ACT_ID",
        "user_id": str(uuid4()),
        "associated_value": "sample value",
        "retailer": "test-retailer",
        "campaigns": ["test-campaign"],
        "data": {
            "foo": "bar",
        },
    }

    def _create_activity(**updated_values: Any) -> Activity:  # noqa: ANN401
        act = Activity(**(payload | updated_values))
        db_session.add(act)
        db_session.commit()
        db_session.refresh(act)
        return act

    return _create_activity
