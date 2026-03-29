from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from advanced_alchemy.base import BigIntAuditBase
from advanced_alchemy.extensions.litestar import (
    AlembicAsyncConfig,
    AsyncSessionConfig,
    EngineConfig,
    SQLAlchemyAsyncConfig,
    async_autocommit_before_send_handler,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from framework.db.engine import create_sqlite_async_engine, get_database_url

__all__ = [
    "Base",
    "create_db_config",
    "create_sqlite_async_engine",
    "get_async_engine",
    "get_database_url",
    "open_async_session",
]


class Base(BigIntAuditBase):
    __abstract__ = True


_db_config: SQLAlchemyAsyncConfig | None = None


def create_db_config() -> SQLAlchemyAsyncConfig:
    global _db_config
    _db_config = SQLAlchemyAsyncConfig(
        connection_string=get_database_url(),
        metadata=Base.metadata,
        create_engine_callable=create_sqlite_async_engine,
        engine_config=EngineConfig(connect_args={"autocommit": False}),
        session_config=AsyncSessionConfig(expire_on_commit=False),
        before_send_handler=async_autocommit_before_send_handler,
        alembic_config=AlembicAsyncConfig(script_location="migrations"),
        create_all=False,
    )
    return _db_config


def _get_config() -> SQLAlchemyAsyncConfig:
    if _db_config is None:
        raise RuntimeError("Database not configured. Call create_db_config() first.")
    return _db_config


def get_async_engine() -> AsyncEngine:
    return _get_config().get_engine()


@asynccontextmanager
async def open_async_session() -> AsyncIterator[AsyncSession]:
    """Open an async database session for non-request code.

    Unlike request-scoped sessions managed by Litestar, callers are responsible
    for committing or rolling back explicitly.
    """
    async with _get_config().get_session() as session:
        yield session
