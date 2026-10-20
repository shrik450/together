"""Typed wrapper around Zendriver, the only module that touches it.

Zendriver is partly untyped: values read from a page arrive as `Any`, and
failures surface as many unrelated exception types. Here, values from the
browser are parsed into declared types, and every failure is raised as a
`BrowserError`.

This module also runs the Chromium process itself and has Zendriver connect to
it. Zendriver's own launcher pipes Chromium's output without reading it or
closing the pipes, which leaks file handles on every restart and can stall
Chromium once a pipe fills.
"""

from __future__ import annotations

import asyncio
import shutil
import socket
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import zendriver
from pydantic import TypeAdapter, ValidationError
from zendriver import cdp

from framework.browser.errors import BrowserError

_EXECUTABLES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
_HOST = "127.0.0.1"
_CONNECT_ATTEMPTS = 40
_CONNECT_INTERVAL = 0.25
_STOP_TIMEOUT = 5


@dataclass(frozen=True, slots=True)
class PausedRequest:
    url: str
    # The tab's own page, as opposed to a frame, image, script or other resource.
    is_page: bool


type RequestFilter = Callable[[PausedRequest], Awaitable[bool]]


class Chromium:
    def __init__(
        self, process: asyncio.subprocess.Process, browser: zendriver.Browser
    ) -> None:
        self._process = process
        self._browser = browser

    @classmethod
    async def start(cls, *, profile_dir: Path, headless: bool) -> Chromium:
        executable = find_executable()
        with _browser_errors("Starting the browser"):
            # Headless Chromium announces itself as "HeadlessChrome".
            user_agent = await _desktop_user_agent(executable) if headless else None
            config = zendriver.Config(
                user_data_dir=profile_dir,
                headless=headless,
                browser_executable_path=executable,
                user_agent=user_agent,
                host=_HOST,
                port=_free_port(),
                browser_connection_max_tries=_CONNECT_ATTEMPTS,
                browser_connection_timeout=_CONNECT_INTERVAL,
            )
            # Zendriver's Config produces its recommended command line.
            process = await asyncio.create_subprocess_exec(
                executable,
                *config(),
                "about:blank",
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                # Given a host and port, Zendriver connects instead of launching.
                browser = await zendriver.start(config)
            except BaseException:
                await _end(process)
                raise
        return cls(process, browser)

    @property
    def running(self) -> bool:
        return self._process.returncode is None

    async def open_tab(self) -> ChromiumTab:
        with _browser_errors("Opening a tab"):
            tab = await self._browser.get("about:blank", new_tab=True)
        return ChromiumTab(tab)

    async def stop(self) -> None:
        try:
            with _browser_errors("Stopping the browser"):
                await self._browser.stop()
        finally:
            await _end(self._process)


class ChromiumTab:
    def __init__(self, tab: zendriver.Tab) -> None:
        self._tab = tab

    async def filter_requests(self, allow: RequestFilter) -> None:
        """Pause every request the tab makes until `allow` decides on it."""

        async def on_request_paused(event: cdp.fetch.RequestPaused) -> None:
            request = PausedRequest(
                url=event.request.url,
                is_page=event.resource_type == cdp.network.ResourceType.DOCUMENT
                and event.frame_id == self._tab.target_id,
            )
            try:
                allowed = await allow(request)
            except Exception:  # noqa: BLE001
                # Zendriver drops handler errors, which would leave the request
                # paused until the page times out. Fail closed instead.
                allowed = False
            if allowed:
                await self._tab.send(cdp.fetch.continue_request(event.request_id))
            else:
                await self._tab.send(
                    cdp.fetch.fail_request(
                        event.request_id, cdp.network.ErrorReason.BLOCKED_BY_CLIENT
                    )
                )

        with _browser_errors("Filtering requests"):
            self._tab.add_handler(cdp.fetch.RequestPaused, on_request_paused)
            await self._tab.send(cdp.fetch.enable())

    async def navigate(self, url: str) -> None:
        with _browser_errors(f"Opening {url}"):
            await self._tab.get(url)
            await self._tab.wait_for_ready_state("complete")

    async def evaluate[T](self, script: str, result: TypeAdapter[T]) -> T:
        with _browser_errors("Reading the page"):
            # Page values arrive untyped; they are parsed just below.
            value = cast(object, await self._tab.evaluate(script))
        try:
            return result.validate_python(value)
        except ValidationError as exc:
            raise BrowserError(f"Unexpected value from the page: {exc}") from exc

    async def close(self) -> None:
        # Closing fails too if the browser has crashed; callers have the
        # original error.
        with suppress(Exception):
            await self._tab.close()


def find_executable() -> str:
    for name in _EXECUTABLES:
        if path := shutil.which(name):
            return path
    raise BrowserError(
        f"No Chromium executable found on PATH (looked for {', '.join(_EXECUTABLES)})"
    )


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind((_HOST, 0))
        # The socket API types addresses as Any; parsed just below.
        address = cast(object, probe.getsockname())
    match address:
        case (str(), int() as port):
            return port
        case _:
            raise BrowserError(f"Unexpected socket address {address!r}")


async def _end(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    process.terminate()
    try:
        async with asyncio.timeout(_STOP_TIMEOUT):
            await process.wait()
    except TimeoutError:
        process.kill()
        await process.wait()


@contextmanager
def _browser_errors(action: str) -> Generator[None]:
    try:
        yield
    except BrowserError:
        raise
    except Exception as exc:
        # Zendriver and Chromium raise a wide range of untyped errors.
        raise BrowserError(f"{action} failed: {exc}") from exc


async def _desktop_user_agent(executable: str) -> str:
    process = await asyncio.create_subprocess_exec(
        executable, "--version", stdout=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    # e.g. "Chromium 155.0.8059.79"
    version = stdout.decode().split()
    if not version:
        raise BrowserError(f"{executable} --version printed nothing")
    major = version[-1].split(".", 1)[0]
    return (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Safari/537.36"
    )
