from __future__ import annotations

from urllib.parse import quote

from litestar.connection import ASGIConnection
from litestar.handlers.base import BaseRouteHandler
from litestar.response import Redirect, Response

from framework.auth.session import normalize_next_url


class AuthRequired(Exception):
    def __init__(self, redirect_to: str) -> None:
        self.redirect_to = redirect_to


def _is_exempt_path(path: str) -> bool:
    if path == "/auth" or path.startswith("/auth/"):
        return True
    return path == "/static" or path.startswith("/static/")


def _build_login_url(connection: ASGIConnection) -> str:
    next_url = connection.url.path
    if connection.url.query:
        next_url = f"{next_url}?{connection.url.query}"
    next_url = normalize_next_url(next_url)
    encoded_next = quote(next_url, safe="/")
    return f"/auth/login?next={encoded_next}"


def require_auth(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Require an authenticated user for non-exempt routes.

    Guards signal unauthenticated access by raising `AuthRequired`; the app-level
    exception handler turns that into either a normal redirect or an HTMX-aware
    `HX-Redirect` response.
    """

    path = connection.url.path
    if _is_exempt_path(path):
        return

    user_id = getattr(connection.state, "user_id", None)
    if user_id is not None:
        return

    raise AuthRequired(redirect_to=_build_login_url(connection))


def auth_required_handler(request, exc: AuthRequired):
    if request.headers.get("HX-Request") == "true":
        return Response(
            content=None,
            headers={"HX-Redirect": exc.redirect_to},
        )
    return Redirect(path=exc.redirect_to)
