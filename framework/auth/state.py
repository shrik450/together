from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from litestar.connection import ASGIConnection
from litestar.types import Scope

_USER_ID_KEY = "user_id"
_CURRENT_USER_KEY = "current_user"


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: int
    username: str


def initialize_auth_state(scope: Scope) -> None:
    """Seed the request state with the auth keys middleware owns.

    Litestar exposes state as a broad mapping, so writes go through one helper to
    keep the concrete auth keys synchronized with the typed read accessors.
    """

    state = _get_scope_state(scope)
    state[_USER_ID_KEY] = None
    state[_CURRENT_USER_KEY] = None


def set_authenticated_user(scope: Scope, user: AuthenticatedUser) -> None:
    state = _get_scope_state(scope)
    state[_USER_ID_KEY] = user.id
    state[_CURRENT_USER_KEY] = user


def get_auth_user_id(connection: ASGIConnection) -> int | None:
    """Contain the untyped Litestar state boundary in one validated accessor."""

    value = connection.state.get(_USER_ID_KEY)
    if value is None:
        return None
    if not isinstance(value, int):
        raise TypeError("Expected auth state user_id to be int | None")
    return value


def get_authenticated_user(connection: ASGIConnection) -> AuthenticatedUser | None:
    """Contain the untyped Litestar state boundary in one validated accessor."""

    value = connection.state.get(_CURRENT_USER_KEY)
    if value is None:
        return None
    if not isinstance(value, AuthenticatedUser):
        raise TypeError(
            "Expected auth state current_user to be AuthenticatedUser | None"
        )
    return value


def _get_scope_state(scope: Scope) -> dict[str, Any]:
    state = scope.setdefault("state", {})
    if not isinstance(state, dict):
        raise TypeError("Expected ASGI scope state to be a dict")
    return state
