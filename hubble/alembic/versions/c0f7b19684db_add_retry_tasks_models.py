"""add retry tasks models

Revision ID: c0f7b19684db
Revises: 7d573978e8cc
Create Date: 2023-03-09 14:35:35.639490

"""
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "c0f7b19684db"
down_revision = "7d573978e8cc"
branch_labels = None
depends_on = None


taskparamskeytypes_enum = sa.Enum(
    "STRING", "INTEGER", "FLOAT", "BOOLEAN", "DATE", "DATETIME", "JSON", name="taskparamskeytypes"
)
retrytaskstatuses_enum = sa.Enum(
    "PENDING",
    "IN_PROGRESS",
    "RETRYING",
    "FAILED",
    "SUCCESS",
    "WAITING",
    "CANCELLED",
    "REQUEUED",
    "CLEANUP",
    "CLEANUP_FAILED",
    name="retrytaskstatuses",
)
task_type_data = {
    "name": "anonymise-activities",
    "path": "hubble.tasks.right_to_be_forgotten.anonymise_activities",
    "error_handler_path": "hubble.tasks.error_handlers.default_handler",
    "keys": [
        {"name": "retailer_slug", "type": "STRING"},
        {"name": "account_holder_uuid", "type": "STRING"},
        {"name": "account_holder_email", "type": "STRING"},
    ],
}


def insert_task_data(conn: sa.engine.Connection) -> None:
    metadata = sa.MetaData()
    task_type = sa.Table("task_type", metadata, autoload_with=conn)
    task_type_key = sa.Table("task_type_key", metadata, autoload_with=conn)

    inserted_obj = conn.execute(
        task_type.insert().values(
            name=task_type_data["name"],
            path=task_type_data["path"],
            error_handler_path=task_type_data["error_handler_path"],
            queue_name="hubble:default",
        )
    )
    conn.execute(
        task_type_key.insert().values(task_type_id=inserted_obj.inserted_primary_key[0]), task_type_data["keys"]
    )


def upgrade() -> None:
    op.create_table(
        "task_type",
        sa.Column("task_type_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("cleanup_handler_path", sa.String(), nullable=True),
        sa.Column("error_handler_path", sa.String(), nullable=False),
        sa.Column("queue_name", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"), nullable=False
        ),
        sa.PrimaryKeyConstraint("task_type_id"),
    )
    op.create_index(op.f("ix_task_type_name"), "task_type", ["name"], unique=True)
    op.create_table(
        "retry_task",
        sa.Column("retry_task_id", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("audit_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("next_attempt_time", sa.DateTime(), nullable=True),
        sa.Column("status", retrytaskstatuses_enum, nullable=False),
        sa.Column("task_type_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"), nullable=False
        ),
        sa.ForeignKeyConstraint(["task_type_id"], ["task_type.task_type_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("retry_task_id"),
    )
    op.create_index(op.f("ix_retry_task_status"), "retry_task", ["status"], unique=False)
    op.create_table(
        "task_type_key",
        sa.Column("task_type_key_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", taskparamskeytypes_enum, nullable=False),
        sa.Column("task_type_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"), nullable=False
        ),
        sa.ForeignKeyConstraint(["task_type_id"], ["task_type.task_type_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_type_key_id"),
        sa.UniqueConstraint("name", "task_type_id", name="name_task_type_id_unq"),
    )
    op.create_table(
        "task_type_key_value",
        sa.Column("value", sa.String(), nullable=True),
        sa.Column("retry_task_id", sa.Integer(), nullable=False),
        sa.Column("task_type_key_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"), nullable=False
        ),
        sa.ForeignKeyConstraint(["retry_task_id"], ["retry_task.retry_task_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_type_key_id"], ["task_type_key.task_type_key_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("retry_task_id", "task_type_key_id"),
    )
    insert_task_data(op.get_bind())


def downgrade() -> None:
    conn = op.get_bind()
    op.drop_table("task_type_key_value")
    op.drop_table("task_type_key")
    op.drop_index(op.f("ix_retry_task_status"), table_name="retry_task")
    op.drop_table("retry_task")
    op.drop_index(op.f("ix_task_type_name"), table_name="task_type")
    op.drop_table("task_type")
    taskparamskeytypes_enum.drop(conn, checkfirst=False)
    retrytaskstatuses_enum.drop(conn, checkfirst=False)
