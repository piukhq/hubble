from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app import settings

if settings.USE_NULL_POOL:
    null_pool = {"poolclass": NullPool}
else:
    null_pool = {}  # pragma: no cover

sync_engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True, echo=settings.SQL_DEBUG, future=True, **null_pool
)
SyncSessionMaker = sessionmaker(bind=sync_engine, future=True, expire_on_commit=False)
