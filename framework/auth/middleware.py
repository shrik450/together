from __future__ import annotations

from typing import override

from litestar import Request
from litestar.datastructures import State
from litestar.middleware import ASGIMiddleware
from litestar.types import ASGIApp, Receive, Scope, Send
from sqlalchemy import select

from framework.auth.models import User
from framework.auth.session import get_session_config, parse_session_cookie
from framework.auth.state import (
    AuthenticatedUser,
    initialize_auth_state,
    set_authenticated_user,
)
from framework.db import open_async_session


def _is_static_path(scope: Scope) -> bool:
    return scope["path"].startswith("/static")


class SessionMiddleware(ASGIMiddleware):
    """Load auth state from the signed session cookie into request.state.

    The middleware stores a lightweight authenticated-user snapshot rather than
    a live ORM instance so later code can load `User` through the request-scoped
    session when needed.
    """

    should_bypass_for_scope = staticmethod(_is_static_path)

    def __init__(self) -> None:
        self._session_config = get_session_config()

    @override
    async def handle(
        self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp
    ) -> None:
        initialize_auth_state(scope)

        request: Request[object, object, State] = Request(scope, receive)
        cookie = request.cookies.get(self._session_config.cookie_name)
        if cookie:
            user_id = parse_session_cookie(cookie, self._session_config)
            if user_id is not None:
                async with open_async_session() as session:
                    row = (
                        await session.execute(
                            select(User.id, User.username).where(User.id == user_id)
                        )
                    ).one_or_none()
                if row is not None:
                    found_id, username = row
                    set_authenticated_user(
                        scope, AuthenticatedUser(id=found_id, username=username)
                    )

        await next_app(scope, receive, send)
