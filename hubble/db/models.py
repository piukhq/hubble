from typing import Any

from sqlalchemy import Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import declarative_base

Base: Any = declarative_base()

utc_timestamp_sql = text("TIMEZONE('utc', CURRENT_TIMESTAMP)")


class Activity(Base):
    __tablename__ = "activity"

    id = Column(UUID(as_uuid=True), primary_key=True)
    type = Column(String, index=True, nullable=False)
    datetime = Column(
        DateTime, index=True, nullable=False, doc="The time at which this activity happened on the publisher side"
    )
    underlying_datetime = Column(
        DateTime,
        index=True,
        nullable=False,
        doc="Timestamp associated with the underlying object e.g. transaction timestamp",
    )
    summary = Column(String, index=True, nullable=False)
    reasons = Column(ARRAY(String), index=True, nullable=False)
    activity_identifier = Column(String, index=True, nullable=False)
    user_id = Column(String, index=True, nullable=False)
    associated_value = Column(String, index=True, nullable=False)
    retailer = Column(String, index=True, nullable=False)
    campaigns = Column(ARRAY(String), nullable=False, index=True)
    data = Column(MutableDict.as_mutable(JSONB), server_default=text("'{}'::jsonb"), nullable=False)
    created_at = Column(DateTime, server_default=utc_timestamp_sql, index=True, nullable=False)
