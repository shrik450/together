from __future__ import annotations

from dataclasses import dataclass

from litestar import Request
from litestar.middleware.base import AbstractMiddleware
from sqlalchemy import select

from framework.auth.models import User
from framework.auth.session import get_session_config, parse_session_cookie
from framework.db import open_async_session


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: int
    username: str


class SessionMiddleware(AbstractMiddleware):
    """Load auth state from the signed session cookie into request.state.

    The middleware stores a lightweight authenticated-user snapshot rather than
    a live ORM instance so later code can load `User` through the request-scoped
    session when needed.
    """

    exclude = ["/static", "/static/*"]

    def __init__(self, app, **kwargs) -> None:
        super().__init__(app, **kwargs)
        self._session_config = get_session_config()

    async def __call__(self, scope, receive, send) -> None:
        scope.setdefault("state", {})
        scope["state"]["user_id"] = None
        scope["state"]["current_user"] = None

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
                    scope["state"]["user_id"] = user.id
                    scope["state"]["current_user"] = AuthenticatedUser(
                        id=user.id,
                        username=user.username,
                    )

        await self.app(scope, receive, send)
