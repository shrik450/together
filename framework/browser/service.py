"""Framework-owned browser for reading the web.

Sites increasingly block plain HTTP clients and datacenter fetchers, so pages
are loaded in a real Chromium driven by Zendriver, which talks to the browser
directly instead of through Playwright or webdriver. The browser keeps a
persistent profile so cookies and consent choices survive between runs, starts
on first use, and closes again after a period without use.

Callers, including LLM tools, choose the URLs, and the app runs on a home
server. Requests to private, loopback and link-local addresses are refused,
both for the requested URL and for wherever it redirects.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import shutil
import socket
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import trafilatura
import zendriver
from litestar import Litestar
from sqlalchemy.engine import make_url

from framework.db import get_database_url

LOGGER = logging.getLogger("together.browser")
_BROWSER_EXECUTABLES = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
)
_SETTLE_POLL = 0.5
_SETTLE_MAX_POLLS = 10
_SNAPSHOT_SCRIPT = """
(() => {
  const links = [];
  const seen = new Set();
  for (const anchor of document.querySelectorAll("a[href]")) {
    const url = anchor.href;
    if (!url.startsWith("http") || seen.has(url)) continue;
    seen.add(url);
    const text = (anchor.innerText || "").replace(/\\s+/g, " ").trim();
    links.push({ text: text.slice(0, 200), url });
  }
  return {
    url: location.href,
    title: document.title,
    text: document.body ? document.body.innerText : "",
    html: document.documentElement.outerHTML,
    jsonLd: Array.from(
      document.querySelectorAll('script[type="application/ld+json"]'),
      (script) => script.textContent,
    ),
    links,
  };
})()
"""


class BrowserError(Exception):
    pass


class BlockedUrlError(BrowserError):
    pass


class SearchBlockedError(BrowserError):
    pass


@dataclass(frozen=True, slots=True)
class Link:
    text: str
    url: str


@dataclass(frozen=True, slots=True)
class Page:
    url: str
    title: str
    text: str
    links: Sequence[Link]
    structured_data: Sequence[object]


@dataclass(frozen=True, slots=True)
class BrowserConfig:
    profile_dir: Path
    headless: bool = True
    allow_private_networks: bool = False
    search_url: str = "https://www.google.com/search"
    max_tabs: int = 2
    page_timeout: timedelta = timedelta(seconds=30)
    idle_timeout: timedelta = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class _Snapshot:
    url: str
    title: str
    text: str
    html: str
    json_ld: Sequence[str]
    links: Sequence[Link]


def default_browser_config() -> BrowserConfig:
    database = make_url(get_database_url()).database
    if database is None:
        raise RuntimeError("TOGETHER_DATABASE_URL must point to a database file")
    return BrowserConfig(profile_dir=Path(database).parent / "browser-profile")


class BrowserService:
    def __init__(self, config: BrowserConfig) -> None:
        self._config = config
        self._browser: zendriver.Browser | None = None
        self._lock = asyncio.Lock()
        self._tabs = asyncio.Semaphore(config.max_tabs)
        self._active_tabs = 0
        self._idle_close: asyncio.Task[None] | None = None

    async def fetch(self, url: str) -> Page:
        await self._check_url(url)
        snapshot = await self._load(url)
        await self._check_url(snapshot.url)

        text = trafilatura.extract(
            snapshot.html,
            url=snapshot.url,
            output_format="markdown",
            favor_recall=True,
        )
        return Page(
            url=snapshot.url,
            title=snapshot.title,
            # Pages built from widgets rather than prose have no main content
            # for trafilatura to find; their visible text is the content.
            text=text or snapshot.text,
            links=snapshot.links,
            structured_data=parse_json_ld(snapshot.json_ld),
        )

    async def search(self, query: str) -> Page:
        url = f"{self._config.search_url}?{urlencode({'q': query, 'hl': 'en'})}"
        snapshot = await self._load(url)
        if is_search_blocked(snapshot.url):
            raise SearchBlockedError(f"Search was blocked ({snapshot.url})")

        return Page(
            url=snapshot.url,
            title=snapshot.title,
            text=snapshot.text,
            links=search_result_links(snapshot.links),
            structured_data=(),
        )

    async def close(self) -> None:
        async with self._lock:
            if self._idle_close is not None:
                self._idle_close.cancel()
                self._idle_close = None
            await self._stop_browser()

    async def _check_url(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise BlockedUrlError(f"Only http and https URLs can be opened: {url}")
        if self._config.allow_private_networks:
            return

        try:
            addresses = await asyncio.get_running_loop().getaddrinfo(
                parts.hostname, parts.port or 443, type=socket.SOCK_STREAM
            )
        except socket.gaierror as exc:
            raise BrowserError(f"Could not resolve {parts.hostname}") from exc

        for *_, sockaddr in addresses:
            if not is_public_address(str(sockaddr[0])):
                raise BlockedUrlError(
                    f"{parts.hostname} resolves to a non-public address"
                )

    async def _load(self, url: str) -> _Snapshot:
        async with self._tabs, self._tab_slot():
            browser = await self._ensure_browser()
            tab: zendriver.Tab | None = None
            try:
                async with asyncio.timeout(self._config.page_timeout.total_seconds()):
                    tab = await browser.get(url, new_tab=True)
                    await _wait_until_settled(tab)
                    raw = await tab.evaluate(_SNAPSHOT_SCRIPT)
            except TimeoutError as exc:
                raise BrowserError(f"Timed out loading {url}") from exc
            finally:
                if tab is not None:
                    await tab.close()

        if not isinstance(raw, dict):
            raise BrowserError(f"Could not read {url}")
        return _Snapshot(
            url=str(raw["url"]),
            title=str(raw["title"]),
            text=str(raw["text"]),
            html=str(raw["html"]),
            json_ld=tuple(str(item) for item in raw["jsonLd"]),
            links=tuple(
                Link(text=str(link["text"]), url=str(link["url"]))
                for link in raw["links"]
            ),
        )

    @asynccontextmanager
    async def _tab_slot(self) -> AsyncIterator[None]:
        async with self._lock:
            if self._idle_close is not None:
                self._idle_close.cancel()
                self._idle_close = None
            self._active_tabs += 1
        try:
            yield
        finally:
            async with self._lock:
                self._active_tabs -= 1
                if self._active_tabs == 0 and self._browser is not None:
                    self._idle_close = asyncio.create_task(self._close_when_idle())

    async def _close_when_idle(self) -> None:
        await asyncio.sleep(self._config.idle_timeout.total_seconds())
        async with self._lock:
            if self._active_tabs == 0:
                self._idle_close = None
                await self._stop_browser()

    async def _ensure_browser(self) -> zendriver.Browser:
        async with self._lock:
            if self._browser is None or self._browser.stopped:
                self._browser = await self._start_browser()
            return self._browser

    async def _start_browser(self) -> zendriver.Browser:
        executable = find_browser_executable()
        self._config.profile_dir.mkdir(parents=True, exist_ok=True)
        LOGGER.info("Starting browser", extra={"executable": executable})
        return await zendriver.start(
            zendriver.Config(
                user_data_dir=self._config.profile_dir,
                headless=self._config.headless,
                browser_executable_path=executable,
                # Headless Chromium announces itself as "HeadlessChrome".
                user_agent=await _desktop_user_agent(executable)
                if self._config.headless
                else None,
            )
        )

    async def _stop_browser(self) -> None:
        if self._browser is None:
            return
        LOGGER.info("Stopping browser")
        browser, self._browser = self._browser, None
        await browser.stop()


def find_browser_executable() -> str:
    for name in _BROWSER_EXECUTABLES:
        if path := shutil.which(name):
            return path
    raise BrowserError(
        "No Chromium executable found on PATH (looked for "
        + ", ".join(_BROWSER_EXECUTABLES)
        + ")"
    )


def is_public_address(address: str) -> bool:
    return ipaddress.ip_address(address.split("%", 1)[0]).is_global


def is_search_blocked(url: str) -> bool:
    parts = urlsplit(url)
    return parts.path.startswith("/sorry/") or parts.hostname == "consent.google.com"


def search_result_links(links: Sequence[Link]) -> Sequence[Link]:
    results: list[Link] = []
    seen: set[str] = set()
    for link in links:
        url = _result_url(link.url)
        if url is None or link.text in {"", "Read more"} or url in seen:
            continue
        seen.add(url)
        results.append(Link(text=link.text, url=url))
    return tuple(results)


def parse_json_ld(blocks: Sequence[str]) -> Sequence[object]:
    parsed: list[object] = []
    for block in blocks:
        try:
            parsed.append(json.loads(block))
        except json.JSONDecodeError:
            continue
    return tuple(parsed)


def _result_url(url: str) -> str | None:
    parts = urlsplit(url)
    if not _is_search_engine_host(parts.hostname or ""):
        return url
    # Google links results through redirects. `/url` carries the target in its
    # query; `/goto` carries an opaque token, and the browser follows it.
    if parts.path == "/url":
        query = parse_qs(parts.query)
        target = query.get("q") or query.get("url")
        return target[0] if target else None
    if parts.path == "/goto":
        return url
    return None


def _is_search_engine_host(hostname: str) -> bool:
    labels = hostname.split(".")
    return "google" in labels or hostname.endswith(
        (".gstatic.com", ".googleusercontent.com")
    )


async def _wait_until_settled(tab: zendriver.Tab) -> None:
    # Many restaurant sites render their content with JavaScript after the load
    # event, so wait until the visible text stops changing.
    await tab.wait_for_ready_state("complete")
    previous = -1
    for _ in range(_SETTLE_MAX_POLLS):
        length = await tab.evaluate(
            "document.body ? document.body.innerText.length : 0"
        )
        if length == previous:
            return
        previous = length
        await asyncio.sleep(_SETTLE_POLL)


async def _desktop_user_agent(executable: str) -> str:
    process = await asyncio.create_subprocess_exec(
        executable, "--version", stdout=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    version = stdout.decode().split()[-1]
    major = version.split(".", 1)[0]
    return (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Safari/537.36"
    )


_service: BrowserService | None = None


def get_browser_service() -> BrowserService:
    if _service is None:
        raise RuntimeError("Browser service is not available")
    return _service


@asynccontextmanager
async def browser_lifespan(_app: Litestar) -> AsyncIterator[None]:
    global _service
    _service = BrowserService(default_browser_config())
    try:
        yield
    finally:
        service, _service = _service, None
        await service.close()
