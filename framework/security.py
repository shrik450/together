from __future__ import annotations

from litestar.datastructures import MutableScopeHeaders
from litestar.middleware.base import AbstractMiddleware


class SecurityHeadersMiddleware(AbstractMiddleware):
    async def __call__(self, scope, receive, send) -> None:
        async def send_wrapper(message) -> None:
            if message.get("type") == "http.response.start":
                headers = MutableScopeHeaders.from_message(message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            await send(message)

        await self.app(scope, receive, send_wrapper)
