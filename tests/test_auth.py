from __future__ import annotations

from types import SimpleNamespace

import pytest
from itsdangerous import URLSafeTimedSerializer
from litestar.response import Redirect, Response, Template
from litestar.testing import RequestFactory

from framework.auth.dependencies import get_current_user_template, provide_current_user
from framework.auth.guards import AuthRequired, auth_required_handler, require_auth
from framework.auth.handlers import login_page, logout
from framework.auth.middleware import AuthenticatedUser, SessionMiddleware
from framework.auth.session import (
    create_session_cookie,
    get_session_config,
    is_safe_redirect,
    normalize_next_url,
    parse_session_cookie,
)
from framework.db import open_async_session


def _set_session_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    secret_key: str = "0123456789abcdef0123456789abcdef",
    max_age_days: str | None = None,
    secure_cookies: str | None = None,
) -> None:
    monkeypatch.setenv("TOGETHER_SECRET_KEY", secret_key)
    if max_age_days is None:
        monkeypatch.delenv("SESSION_MAX_AGE_DAYS", raising=False)
    else:
        monkeypatch.setenv("SESSION_MAX_AGE_DAYS", max_age_days)
    if secure_cookies is None:
        monkeypatch.delenv("TOGETHER_SECURE_COOKIES", raising=False)
    else:
        monkeypatch.setenv("TOGETHER_SECURE_COOKIES", secure_cookies)
    get_session_config.cache_clear()


def _make_connection(
    path: str, query: str = "", user_id: int | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        url=SimpleNamespace(path=path, query=query),
        state={"user_id": user_id},
    )


class TestSessionConfig:
    @pytest.mark.parametrize(
        ("secret_key", "message"),
        [
            (None, "TOGETHER_SECRET_KEY is required"),
            ("short", "TOGETHER_SECRET_KEY must be at least 32 characters"),
        ],
    )
    def test_rejects_missing_or_short_secret_key(
        self,
        monkeypatch: pytest.MonkeyPatch,
        secret_key: str | None,
        message: str,
    ) -> None:
        if secret_key is None:
            monkeypatch.delenv("TOGETHER_SECRET_KEY", raising=False)
        else:
            monkeypatch.setenv("TOGETHER_SECRET_KEY", secret_key)
        monkeypatch.delenv("SESSION_MAX_AGE_DAYS", raising=False)
        monkeypatch.delenv("TOGETHER_SECURE_COOKIES", raising=False)
        get_session_config.cache_clear()

        with pytest.raises(RuntimeError, match=message):
            get_session_config()

    @pytest.mark.parametrize(
        ("value", "expected_seconds"),
        [(None, 30 * 24 * 60 * 60), ("1", 24 * 60 * 60), ("7", 7 * 24 * 60 * 60)],
    )
    def test_parses_session_max_age(
        self,
        monkeypatch: pytest.MonkeyPatch,
        value: str | None,
        expected_seconds: int,
    ) -> None:
        _set_session_env(monkeypatch, max_age_days=value)

        assert get_session_config().max_age_seconds == expected_seconds

    @pytest.mark.parametrize("value", ["0", "-1", "abc"])
    def test_rejects_invalid_max_age(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        _set_session_env(monkeypatch, max_age_days=value)

        with pytest.raises(ValueError, match="SESSION_MAX_AGE_DAYS"):
            get_session_config()

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(None, True), ("true", True), ("1", True), ("false", False), ("0", False)],
    )
    def test_parses_secure_cookie_flag(
        self,
        monkeypatch: pytest.MonkeyPatch,
        value: str | None,
        expected: bool,
    ) -> None:
        _set_session_env(monkeypatch, secure_cookies=value)

        assert get_session_config().secure_cookies is expected


class TestSessionCookies:
    def test_round_trips_session_cookie(self) -> None:
        config = get_session_config()
        cookie = create_session_cookie(42, config)

        assert parse_session_cookie(cookie, config) == 42

    def test_returns_none_for_tampered_cookie(self) -> None:
        config = get_session_config()
        cookie = create_session_cookie(42, config)

        assert parse_session_cookie(f"{cookie}tampered", config) is None

    def test_returns_none_for_non_integer_user_id(self) -> None:
        config = get_session_config()
        serializer = URLSafeTimedSerializer(config.secret_key, salt="together.session")
        cookie = serializer.dumps({"user_id": "42"})

        assert parse_session_cookie(cookie, config) is None


class TestRedirectValidation:
    @pytest.mark.parametrize(
        ("url", "expected_safe", "expected_normalized"),
        [
            ("/", True, "/"),
            ("/auth/login?next=/", True, "/auth/login?next=/"),
            ("relative/path", False, "/"),
            ("https://example.com", False, "/"),
            ("//example.com", False, "/"),
            ("javascript:alert(1)", False, "/"),
            (None, False, "/"),
        ],
    )
    def test_redirect_safety(
        self, url: str | None, expected_safe: bool, expected_normalized: str
    ) -> None:
        assert is_safe_redirect(url) is expected_safe
        assert normalize_next_url(url) == expected_normalized


class TestAuthGuard:
    @pytest.mark.parametrize(
        "path", ["/auth/login", "/auth/logout", "/static/style.css"]
    )
    def test_exempt_paths_bypass_auth(self, path: str) -> None:
        require_auth(_make_connection(path), object())

    def test_authenticated_request_passes(self) -> None:
        require_auth(_make_connection("/", user_id=1), object())

    def test_unauthenticated_request_raises_with_safe_next_url(self) -> None:
        connection = _make_connection("/journal", query="page=2")

        with pytest.raises(AuthRequired) as exc_info:
            require_auth(connection, object())

        assert exc_info.value.redirect_to == "/auth/login?next=/journal%3Fpage%3D2"

    def test_auth_required_handler_returns_htmx_redirect(self) -> None:
        request = SimpleNamespace(headers={"HX-Request": "true"})

        response = auth_required_handler(request, AuthRequired("/auth/login?next=/"))

        assert isinstance(response, Response)
        assert response.headers["HX-Redirect"] == "/auth/login?next=/"

    def test_auth_required_handler_returns_normal_redirect(self) -> None:
        request = SimpleNamespace(headers={})

        response = auth_required_handler(request, AuthRequired("/auth/login?next=/"))

        assert isinstance(response, Redirect)
        assert str(response.url) == "/auth/login?next=/"


class TestAuthHandlers:
    async def test_login_page_renders_for_anonymous_user(self) -> None:
        request = RequestFactory().get("/auth/login", query_params={"next": "/journal"})

        response = await login_page.fn(request)

        assert isinstance(response, Template)
        assert response.context["next"] == "/journal"
        assert response.context["error"] is None

    async def test_login_page_redirects_when_already_authenticated(self) -> None:
        request = RequestFactory().get(
            "/auth/login",
            query_params={"next": "/journal"},
            state={"user_id": 1},
        )

        response = await login_page.fn(request)

        assert isinstance(response, Redirect)
        assert str(response.url) == "/journal"

    async def test_login_submit_sets_cookie_and_redirects(
        self, client, user_factory
    ) -> None:
        await user_factory("sam", "password123")

        response = await client.post(
            "/auth/login",
            data={"username": "sam", "password": "password123", "next": "/journal"},
            follow_redirects=False,
        )

        assert response.status_code in {302, 303, 307, 308}
        assert response.headers["location"] == "/journal"
        assert "session=" in response.headers["set-cookie"]

    async def test_login_submit_rejects_invalid_credentials(
        self, client, user_factory
    ) -> None:
        await user_factory("sam", "password123")

        response = await client.post(
            "/auth/login",
            data={"username": "sam", "password": "wrong-password", "next": "/journal"},
        )

        assert response.status_code == 200
        assert "Invalid username or password" in response.text
        assert 'value="sam"' in response.text

    async def test_login_submit_normalizes_malicious_next(
        self, client, user_factory
    ) -> None:
        await user_factory("sam", "password123")

        response = await client.post(
            "/auth/login",
            data={
                "username": "sam",
                "password": "password123",
                "next": "https://example.com",
            },
            follow_redirects=False,
        )

        assert response.headers["location"] == "/"

    async def test_logout_clears_cookie(self) -> None:
        response = await logout.fn()

        assert str(response.url) == "/auth/login"
        assert len(response.cookies) == 1
        assert response.cookies[0].key == "session"
        assert response.cookies[0].max_age == 0


class TestAuthMiddleware:
    async def _run_middleware(self, cookie: str | None) -> dict[str, str | int | None]:
        captured: dict[str, str | int | None] = {}

        async def terminal_app(scope, receive, send) -> None:
            current_user = scope["state"]["current_user"]
            captured["user_id"] = scope["state"]["user_id"]
            captured["username"] = (
                None if current_user is None else current_user.username
            )
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        middleware = SessionMiddleware(terminal_app)
        request = RequestFactory().get(
            "/",
            cookies=None if cookie is None else f"session={cookie}",
        )

        async def receive() -> dict[str, str]:
            return {"type": "http.request"}

        async def send(_message) -> None:
            return None

        await middleware(request.scope, receive, send)
        return captured

    async def test_anonymous_request_stays_anonymous(self) -> None:
        state = await self._run_middleware(cookie=None)

        assert state == {"user_id": None, "username": None}

    async def test_valid_cookie_populates_auth_state(self, user_factory) -> None:
        user = await user_factory("sam", "password123")
        cookie = create_session_cookie(user.id, get_session_config())

        state = await self._run_middleware(cookie=cookie)

        assert state == {"user_id": user.id, "username": "sam"}

    async def test_cookie_for_missing_user_stays_anonymous(self) -> None:
        cookie = create_session_cookie(9999, get_session_config())

        state = await self._run_middleware(cookie=cookie)

        assert state == {"user_id": None, "username": None}


class TestCurrentUserDependency:
    async def test_provide_current_user_returns_none_when_unauthenticated(self) -> None:
        request = RequestFactory().get("/", state={})

        async with open_async_session() as session:
            current_user = await provide_current_user(request, session)

        assert current_user is None

    async def test_provide_current_user_returns_user(self, user_factory) -> None:
        user = await user_factory("sam", "password123")
        request = RequestFactory().get("/", state={"user_id": user.id})

        async with open_async_session() as session:
            current_user = await provide_current_user(request, session)

        assert current_user is not None
        assert current_user.username == "sam"

    def test_get_current_user_template_reads_snapshot_from_request_state(self) -> None:
        request = RequestFactory().get(
            "/",
            state={"current_user": AuthenticatedUser(id=1, username="sam")},
        )

        current_user = get_current_user_template({"request": request})

        assert current_user == AuthenticatedUser(id=1, username="sam")
