from __future__ import annotations


class TestAppWiring:
    async def test_login_route_is_available(self, client) -> None:
        response = await client.get("/auth/login")

        assert response.status_code == 200
        assert "Log in" in response.text

    async def test_static_route_is_available_without_auth(self, client) -> None:
        response = await client.get("/static/style.css")

        assert response.status_code == 200
        assert "--bg:" in response.text

    async def test_security_headers_are_present(self, client) -> None:
        response = await client.get("/auth/login")

        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in response.headers["content-security-policy"]


class TestProtectedHome:
    async def test_home_redirects_when_unauthenticated(self, client) -> None:
        response = await client.get("/", follow_redirects=False)

        assert response.status_code in {302, 303, 307, 308}
        assert response.headers["location"] == "/auth/login?next=/"

    async def test_home_returns_hx_redirect_for_htmx_requests(self, client) -> None:
        response = await client.get("/", headers={"HX-Request": "true"})

        assert response.status_code == 200
        assert response.headers["HX-Redirect"] == "/auth/login?next=/"


class TestShellRendering:
    async def test_authenticated_home_renders_shell(self, client, user_factory) -> None:
        await user_factory("sam", "password123")
        await client.post(
            "/auth/login",
            data={"username": "sam", "password": "password123", "next": "/"},
            follow_redirects=False,
        )
        response = await client.get("/")

        assert response.status_code == 200
        assert "Welcome to Together" in response.text
        assert "shell-sidebar" in response.text
        assert "shell-topbar" in response.text
        assert "sam" in response.text
        assert "Logout" in response.text
