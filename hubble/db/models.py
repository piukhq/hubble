from datetime import datetime as dt
from uuid import UUID

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


utc_timestamp_sql = text("TIMEZONE('utc', CURRENT_TIMESTAMP)")


class Activity(Base):
    __tablename__ = "activity"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(index=True, nullable=False)
    datetime: Mapped[dt] = mapped_column(
        index=True, nullable=False, doc="The time at which this activity happened on the publisher side"
    )
    underlying_datetime: Mapped[dt] = mapped_column(
        index=True, nullable=False, doc="Timestamp associated with the underlying object e.g. transaction timestamp"
    )
    summary: Mapped[str] = mapped_column(index=True, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(ARRAY(String), index=True, nullable=False)
    activity_identifier: Mapped[str] = mapped_column(index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(index=True, nullable=False)
    associated_value: Mapped[str] = mapped_column(index=True, nullable=False)
    retailer: Mapped[str] = mapped_column(index=True, nullable=False)
    campaigns: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, index=True)
    data: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    created_at: Mapped[dt] = mapped_column(server_default=utc_timestamp_sql, index=True, nullable=False)
