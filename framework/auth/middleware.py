from __future__ import annotations

from typing import Any

from litestar import Request
from litestar.middleware.base import AbstractMiddleware
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


class SessionMiddleware(AbstractMiddleware):
    """Load auth state from the signed session cookie into request.state.

    The middleware stores a lightweight authenticated-user snapshot rather than
    a live ORM instance so later code can load `User` through the request-scoped
    session when needed.
    """

    exclude = ["/static", "/static/*"]

    def __init__(self, app: ASGIApp, **kwargs: Any) -> None:
        super().__init__(app, **kwargs)
        self._session_config = get_session_config()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
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

        await self.app(scope, receive, send)
