from __future__ import annotations

from litestar.datastructures import MutableScopeHeaders
from litestar.middleware.base import AbstractMiddleware
from litestar.types import Message, Receive, Scope, Send


class SecurityHeadersMiddleware(AbstractMiddleware):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableScopeHeaders.from_message(message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Content-Security-Policy"] = (
                    "default-src 'self'; script-src 'self'; style-src 'self'"
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)
