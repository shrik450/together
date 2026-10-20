"""Framework-owned browser for reading the web.

Sites increasingly block plain HTTP clients and datacenter fetchers, so pages
are loaded in a real Chromium (see `chromium.py`). The browser keeps a
persistent profile so cookies and consent choices survive between runs, starts
on first use, and closes again after a period without use.

Every request a tab makes goes through `RequestGuard`, which refuses
non-public addresses.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import trafilatura
from litestar import Litestar
from pydantic import TypeAdapter
from sqlalchemy.engine import make_url

from framework.browser.chromium import Chromium, ChromiumTab
from framework.browser.errors import BlockedUrlError, BrowserError, SearchBlockedError
from framework.browser.network import IPAddress, RequestGuard
from framework.browser.page import Link, Page, parse_json_ld
from framework.browser.search import is_search_blocked, search_result_links
from framework.db import get_database_url

LOGGER = logging.getLogger("together.browser")
_SETTLE_POLL = 0.5
_SETTLE_MAX_POLLS = 10
_TEXT_LENGTH_SCRIPT = "document.body ? document.body.innerText.length : 0"
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
    json_ld: Array.from(
      document.querySelectorAll('script[type="application/ld+json"]'),
      (script) => script.textContent,
    ),
    links,
  };
})()
"""


@dataclass(frozen=True, slots=True)
class BrowserConfig:
    profile_dir: Path
    headless: bool = True
    # Tests serve pages from loopback addresses, which are otherwise refused.
    allowed_private_addresses: frozenset[IPAddress] = frozenset()
    # Search parsing is Google-specific; tests point this at a fake results page.
    google_search_url: str = "https://www.google.com/search"
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


_SNAPSHOT = TypeAdapter(_Snapshot)
_TEXT_LENGTH = TypeAdapter(int)


def default_browser_config() -> BrowserConfig:
    database = make_url(get_database_url()).database
    if database is None:
        raise RuntimeError("TOGETHER_DATABASE_URL must point to a database file")
    return BrowserConfig(profile_dir=Path(database).parent / "browser-profile")


class BrowserService:
    def __init__(self, config: BrowserConfig) -> None:
        self._config: BrowserConfig = config
        self._chromium: Chromium | None = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._tabs: asyncio.Semaphore = asyncio.Semaphore(config.max_tabs)
        self._active_tabs: int = 0
        self._idle_close: asyncio.Task[None] | None = None

    async def fetch(self, url: str) -> Page:
        snapshot = await self._load(url)
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
        query_string = urlencode({"q": query, "hl": "en"})
        snapshot = await self._load(f"{self._config.google_search_url}?{query_string}")
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

    async def _load(self, url: str) -> _Snapshot:
        if urlsplit(url).scheme not in {"http", "https"}:
            raise BlockedUrlError(f"Only http and https URLs can be opened: {url}")

        async with self._tabs, self._tab_slot():
            chromium = await self._ensure_browser()
            tab = await chromium.open_tab()
            try:
                async with asyncio.timeout(self._config.page_timeout.total_seconds()):
                    return await self._load_in(tab, url)
            except TimeoutError as exc:
                raise BrowserError(f"Timed out loading {url}") from exc
            finally:
                await tab.close()

    async def _load_in(self, tab: ChromiumTab, url: str) -> _Snapshot:
        guard = RequestGuard(self._config.allowed_private_addresses)
        await guard.install(tab)
        await tab.navigate(url)
        await _wait_until_settled(tab)
        if guard.blocked_page is not None:
            raise BlockedUrlError(
                f"Refused to load {guard.blocked_page}: it is not on a public address"
            )
        return await tab.evaluate(_SNAPSHOT_SCRIPT, _SNAPSHOT)

    @asynccontextmanager
    async def _tab_slot(self) -> AsyncGenerator[None]:
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
                if self._active_tabs == 0 and self._chromium is not None:
                    self._idle_close = asyncio.create_task(self._close_when_idle())

    async def _close_when_idle(self) -> None:
        await asyncio.sleep(self._config.idle_timeout.total_seconds())
        async with self._lock:
            if self._active_tabs == 0:
                self._idle_close = None
                await self._stop_browser()

    async def _ensure_browser(self) -> Chromium:
        async with self._lock:
            if self._chromium is None or not self._chromium.running:
                self._config.profile_dir.mkdir(parents=True, exist_ok=True)
                LOGGER.info("Starting browser")
                self._chromium = await Chromium.start(
                    profile_dir=self._config.profile_dir,
                    headless=self._config.headless,
                )
            return self._chromium

    async def _stop_browser(self) -> None:
        if self._chromium is None:
            return
        LOGGER.info("Stopping browser")
        chromium, self._chromium = self._chromium, None
        await chromium.stop()


async def _wait_until_settled(tab: ChromiumTab) -> None:
    # Many restaurant sites render their content with JavaScript after the load
    # event, so wait until the visible text stops changing.
    previous: int | None = None
    for _poll in range(_SETTLE_MAX_POLLS):
        length = await tab.evaluate(_TEXT_LENGTH_SCRIPT, _TEXT_LENGTH)
        if length == previous:
            return
        previous = length
        await asyncio.sleep(_SETTLE_POLL)


_service: BrowserService | None = None


def get_browser_service() -> BrowserService:
    if _service is None:
        raise RuntimeError("Browser service is not available")
    return _service


@asynccontextmanager
async def browser_lifespan(_app: Litestar) -> AsyncGenerator[None]:
    global _service
    _service = BrowserService(default_browser_config())
    try:
        yield
    finally:
        service, _service = _service, None
        await service.close()
