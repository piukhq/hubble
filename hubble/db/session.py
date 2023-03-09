from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from hubble.config import settings

null_pool = {"poolclass": NullPool} if settings.USE_NULL_POOL or settings.TESTING else {}  # pragma: no cover

# application_name
CONNECT_ARGS = {"application_name": "hubble"}


engine = create_engine(
    settings.SQLALCHEMY_URI,
    connect_args=CONNECT_ARGS,
    pool_pre_ping=True,
    echo=settings.SQL_DEBUG,
    future=True,
    **null_pool
)

SessionMaker = sessionmaker(bind=engine, future=True, expire_on_commit=False)
