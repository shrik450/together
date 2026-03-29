import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from advanced_alchemy.base import BigIntAuditBase
from advanced_alchemy.extensions.litestar import (
    AlembicAsyncConfig,
    AsyncSessionConfig,
    EngineConfig,
    SQLAlchemyAsyncConfig,
    async_autocommit_before_send_handler,
)
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine


class Base(BigIntAuditBase):
    __abstract__ = True


def _get_database_url() -> str:
    database_url = os.getenv("TOGETHER_DATABASE_URL")
    if not database_url:
        raise RuntimeError("TOGETHER_DATABASE_URL is required")

    url = make_url(database_url)
    if url.drivername != "sqlite+aiosqlite":
        raise RuntimeError("TOGETHER_DATABASE_URL must use sqlite+aiosqlite")

    if url.database in {None, "", ":memory:"} or not Path(url.database).is_absolute():
        raise RuntimeError(
            "TOGETHER_DATABASE_URL must point to an absolute SQLite database path"
        )

    return database_url


def _get_sqlite_connection(dbapi_connection):
    # aiosqlite wraps the real sqlite3 connection behind two layers:
    # the DBAPI adapter's `driver_connection` holds the aiosqlite
    # Connection, whose `_conn` is the underlying sqlite3.Connection.
    # We need the raw sqlite3 connection to issue PRAGMAs outside
    # aiosqlite's async wrapper.  The module check is a fallback for
    # direct sqlite3 connections (e.g., in synchronous Alembic runs).
    sqlite_connection = getattr(dbapi_connection, "driver_connection", None)
    if sqlite_connection is not None:
        sqlite_connection = getattr(sqlite_connection, "_conn", None)

    if sqlite_connection is None and dbapi_connection.__class__.__module__.startswith(
        "sqlite3"
    ):
        sqlite_connection = dbapi_connection

    if sqlite_connection is None:
        raise RuntimeError(
            "Could not access the underlying sqlite3 connection for PRAGMA setup"
        )

    return sqlite_connection


def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    sqlite_connection = _get_sqlite_connection(dbapi_connection)
    original_autocommit = sqlite_connection.autocommit
    # Temporarily enable autocommit so connection-level PRAGMAs take effect immediately.
    sqlite_connection.autocommit = True

    cursor = sqlite_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()
        sqlite_connection.autocommit = original_autocommit


def _create_engine(connection_string: str, **engine_config) -> AsyncEngine:
    engine = create_async_engine(connection_string, **engine_config)
    event.listen(engine.sync_engine, "connect", _configure_sqlite)
    return engine


_db_config: SQLAlchemyAsyncConfig | None = None


def create_db_config() -> SQLAlchemyAsyncConfig:
    global _db_config
    _db_config = SQLAlchemyAsyncConfig(
        connection_string=_get_database_url(),
        metadata=Base.metadata,
        create_engine_callable=_create_engine,
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
