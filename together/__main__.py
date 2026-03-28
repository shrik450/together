from __future__ import annotations

import asyncio
import getpass
import sys

from sqlalchemy.exc import IntegrityError

from framework.auth.models import User
from framework.db import open_async_session


def _print_usage() -> None:
    print("Usage: uv run python -m together create-user <username>")


def _prompt_password() -> str:
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise ValueError("Passwords do not match")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    return password


async def _create_user(username: str) -> int:
    if not username:
        print("Error: Username is required")
        return 1

    try:
        password = _prompt_password()
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    async with open_async_session() as session:
        try:
            user = User(username=username, password_hash=User.hash_password(password))
            session.add(user)
            await session.commit()
        except IntegrityError:
            print(f"Error: User '{username}' already exists")
            return 1

    print(f"User '{username}' created successfully")
    return 0


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] != "create-user":
        _print_usage()
        return 1
    return asyncio.run(_create_user(sys.argv[2]))


if __name__ == "__main__":
    raise SystemExit(main())
