from __future__ import annotations

import asyncio
import importlib
import os
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from litestar.testing import AsyncTestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import framework.scheduler.service as scheduler_service_module
import framework.ui as ui_module
from framework.auth.models import User
from framework.auth.session import get_session_config
from framework.db import Base, create_db_config, get_async_engine, open_async_session
from tests.helpers import reset_scheduler_task_calls

TEST_SECRET_KEY = "0123456789abcdef0123456789abcdef"


@pytest.fixture(scope="session", autouse=True)
def configured_env(
    tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest
) -> str:
    database_path = tmp_path_factory.mktemp("data") / "test.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    os.environ["TOGETHER_DATABASE_URL"] = database_url
    os.environ["TOGETHER_SECRET_KEY"] = TEST_SECRET_KEY
    os.environ["TOGETHER_SECURE_COOKIES"] = "false"
    os.environ.pop("SESSION_MAX_AGE_DAYS", None)
    get_session_config.cache_clear()
    create_db_config()

    def dispose_engine() -> None:
        try:
            asyncio.run(get_async_engine().dispose())
        except RuntimeError:
            return

    request.addfinalizer(dispose_engine)
    return database_url


@pytest.fixture(autouse=True)
def reset_global_state() -> Iterator[None]:
    get_session_config.cache_clear()
    scheduler_service_module._registry.clear()
    ui_module._nav_nodes.clear()
    reset_scheduler_task_calls()
    yield
    get_session_config.cache_clear()
    scheduler_service_module._registry.clear()
    ui_module._nav_nodes.clear()
    reset_scheduler_task_calls()


@pytest.fixture(scope="session")
def database_url(configured_env: str) -> str:
    return configured_env


@pytest.fixture(scope="session")
def litestar_app(configured_env: str):
    import app as app_module

    reloaded = importlib.reload(app_module)
    return reloaded.app


@pytest.fixture
async def reset_database(configured_env: str) -> AsyncIterator[None]:
    engine = get_async_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture
async def client(
    litestar_app: Any, reset_database: None
) -> AsyncIterator[AsyncTestClient[Any]]:
    async with AsyncTestClient(litestar_app) as test_client:
        yield test_client


@pytest.fixture
def user_factory(
    reset_database: None,
) -> Callable[[str, str], Awaitable[User]]:
    async def factory(username: str = "samhita", password: str = "password123") -> User:
        async with open_async_session() as session:
            user = User(
                username=username,
                password_hash=User.hash_password(password),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    return factory
