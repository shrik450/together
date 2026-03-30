from __future__ import annotations

from typing import Any

from litestar import Request
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


class SessionMiddleware(ASGIMiddleware):
    """Load auth state from the signed session cookie into request.state.

    The middleware stores a lightweight authenticated-user snapshot rather than
    a live ORM instance so later code can load `User` through the request-scoped
    session when needed.
    """

    should_bypass_for_scope = staticmethod(
        lambda scope: scope.get("path", "").startswith("/static")
    )

    def __init__(self, app: ASGIApp | None = None, **kwargs: Any) -> None:
        self._app = app
        self._session_config = get_session_config()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if "app" in kwargs and len(kwargs) == 1 and not args:
            return super().__call__(kwargs["app"])
        if len(args) == 1 and not kwargs:
            return super().__call__(args[0])
        if len(args) == 3 and not kwargs and self._app is not None:
            scope, receive, send = args
            return self.handle(scope, receive, send, self._app)
        raise TypeError(
            "SessionMiddleware expected either an app or ASGI call arguments"
        )

    async def handle(
        self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp
    ) -> None:
        initialize_auth_state(scope)

        request = Request(scope, receive)
        cookie = request.cookies.get(self._session_config.cookie_name)
        if cookie:
            user_id = parse_session_cookie(cookie, self._session_config)
            if user_id is not None:
                async with open_async_session() as session:
                    user = (
                        await session.execute(
                            select(User.id, User.username).where(User.id == user_id)
                        )
                    ).one_or_none()
                if user is not None:
                    set_authenticated_user(
                        scope,
                        AuthenticatedUser(id=user.id, username=user.username),
                    )

        await next_app(scope, receive, send)
