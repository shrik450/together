from __future__ import annotations

import re
from pathlib import Path

import pytest

from framework.db.engine import create_sqlite_async_engine, get_database_url


class TestDatabaseUrl:
    @pytest.mark.parametrize(
        ("value", "message"),
        [
            (None, "TOGETHER_DATABASE_URL is required"),
            ("postgresql+asyncpg:///tmp/together.db", "must use sqlite+aiosqlite"),
            (
                "sqlite+aiosqlite:///relative.db",
                "must point to an absolute SQLite database path",
            ),
            (
                "sqlite+aiosqlite:///:memory:",
                "must point to an absolute SQLite database path",
            ),
        ],
    )
    def test_rejects_invalid_database_urls(
        self, monkeypatch: pytest.MonkeyPatch, value: str | None, message: str
    ) -> None:
        if value is None:
            monkeypatch.delenv("TOGETHER_DATABASE_URL", raising=False)
        else:
            monkeypatch.setenv("TOGETHER_DATABASE_URL", value)

        expected_message = (
            message if value is None else f"TOGETHER_DATABASE_URL {message}"
        )
        with pytest.raises(RuntimeError, match=re.escape(expected_message)):
            get_database_url()

    def test_accepts_absolute_sqlite_url(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        database_url = f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite'}"
        monkeypatch.setenv("TOGETHER_DATABASE_URL", database_url)

        assert get_database_url() == database_url


class TestSQLiteConnectionConfiguration:
    async def test_applies_expected_pragmas(self, database_url: str) -> None:
        engine = create_sqlite_async_engine(
            database_url,
            connect_args={"autocommit": False},
        )

        try:
            async with engine.connect() as connection:
                journal_mode = (
                    await connection.exec_driver_sql("PRAGMA journal_mode")
                ).scalar_one()
                synchronous = (
                    await connection.exec_driver_sql("PRAGMA synchronous")
                ).scalar_one()
                foreign_keys = (
                    await connection.exec_driver_sql("PRAGMA foreign_keys")
                ).scalar_one()
                busy_timeout = (
                    await connection.exec_driver_sql("PRAGMA busy_timeout")
                ).scalar_one()
        finally:
            await engine.dispose()

        assert str(journal_mode).lower() == "wal"
        assert int(synchronous) == 1
        assert int(foreign_keys) == 1
        assert int(busy_timeout) == 5000
