"""Keeps the browser off the home network.

Callers, including LLM tools, choose the URLs the browser opens, and the app
runs on a home server. Every request a tab makes (the page, its redirects, and
its images, scripts and frames) is paused and only continues if its host
resolves to public addresses.

Known limits: the address is resolved here and again by Chromium, so a host
that answers differently the second time (DNS rebinding) can get through, and
requests from web workers and WebSockets are not paused.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlsplit

from framework.browser.chromium import ChromiumTab, PausedRequest

LOGGER = logging.getLogger("together.browser")
_NETWORK_SCHEMES = frozenset({"http", "https", "ws", "wss"})
_LOCAL_SCHEMES = frozenset({"about", "blob", "data"})

type IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class RequestGuard:
    """Decides which of one tab's requests may reach the network."""

    def __init__(self, allowed_private: frozenset[IPAddress]) -> None:
        self._allowed_private = allowed_private
        self._hosts: dict[str, bool] = {}
        self.blocked_page: str | None = None

    async def install(self, tab: ChromiumTab) -> None:
        await tab.filter_requests(self._allow)

    async def _allow(self, request: PausedRequest) -> bool:
        if await self._is_allowed(request.url):
            return True
        LOGGER.info("Blocked request", extra={"url": request.url})
        if request.is_page:
            self.blocked_page = request.url
        return False

    async def _is_allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        if parts.scheme in _LOCAL_SCHEMES:
            return True
        if parts.scheme not in _NETWORK_SCHEMES or not parts.hostname:
            return False

        hostname = parts.hostname
        if hostname not in self._hosts:
            self._hosts[hostname] = all(
                is_allowed_address(address, self._allowed_private)
                for address in await resolve(hostname)
            )
        return self._hosts[hostname]


def is_allowed_address(
    address: IPAddress, allowed_private: frozenset[IPAddress]
) -> bool:
    return address.is_global or address in allowed_private


async def resolve(hostname: str) -> list[IPAddress]:
    infos = await asyncio.get_running_loop().getaddrinfo(
        hostname, None, type=socket.SOCK_STREAM
    )
    return [parse_address(str(sockaddr[0])) for *_, sockaddr in infos]


def parse_address(text: str) -> IPAddress:
    # IPv6 link-local addresses carry a zone, as in "fe80::1%eth0".
    return ipaddress.ip_address(text.split("%", 1)[0])
