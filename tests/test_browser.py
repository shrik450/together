from __future__ import annotations

import asyncio
import dataclasses
from datetime import timedelta
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import quote

import pytest
from pydantic import TypeAdapter

from framework.browser import (
    BlockedUrlError,
    BrowserConfig,
    BrowserError,
    BrowserService,
    Link,
    SearchBlockedError,
)
from framework.browser.chromium import Chromium
from framework.browser.network import is_allowed_address, parse_address
from framework.browser.page import parse_json_ld
from framework.browser.search import is_search_blocked, search_result_links
from tests.helpers import RecordingHandler


class TestAddressPolicy:
    @pytest.mark.parametrize(
        ("address", "allowed"),
        [
            ("93.184.215.14", True),
            ("2606:4700::6810:85e5", True),
            ("127.0.0.1", False),
            ("10.0.0.1", False),
            ("192.168.1.1", False),
            ("172.16.0.1", False),
            ("169.254.169.254", False),
            ("100.64.0.1", False),
            ("::1", False),
            ("fe80::1%eth0", False),
            ("fd00::1", False),
            ("::ffff:192.168.1.1", False),
        ],
    )
    def test_only_public_addresses_are_allowed(
        self, address: str, allowed: bool
    ) -> None:
        assert is_allowed_address(parse_address(address), frozenset()) is allowed

    def test_private_addresses_can_be_allowed_one_by_one(self) -> None:
        allowed = frozenset({ip_address("127.0.0.1")})

        assert is_allowed_address(parse_address("127.0.0.1"), allowed)
        assert not is_allowed_address(parse_address("127.0.0.2"), allowed)


class TestSearchResults:
    def test_keeps_result_links_and_drops_search_engine_links(self) -> None:
        links = [
            Link("Images", "https://www.google.com/search?q=x&udm=2"),
            Link("Saperavi: Home", "https://www.google.com/goto?url=abc"),
            Link("Read more", "https://www.google.com/goto?url=def"),
            Link("A review", "https://www.google.com/url?q=https://example.com/r"),
            Link("", "https://example.com/no-text"),
            Link("Site", "https://saperavinyc.com/"),
            Link("Site again", "https://saperavinyc.com/"),
            Link("Logo", "https://lh3.googleusercontent.com/logo.png"),
        ]

        assert search_result_links(links) == (
            Link("Saperavi: Home", "https://www.google.com/goto?url=abc"),
            Link("A review", "https://example.com/r"),
            Link("Site", "https://saperavinyc.com/"),
        )

    @pytest.mark.parametrize(
        ("url", "blocked"),
        [
            ("https://www.google.com/sorry/index?continue=x", True),
            ("https://consent.google.com/ml?continue=x", True),
            ("https://www.google.com/search?q=x", False),
        ],
    )
    def test_detects_blocked_search(self, url: str, blocked: bool) -> None:
        assert is_search_blocked(url) is blocked

    def test_parse_json_ld_skips_invalid_blocks(self) -> None:
        assert parse_json_ld(['{"@type": "Restaurant"}', "{not json"]) == (
            {"@type": "Restaurant"},
        )


class TestChromium:
    async def test_page_values_are_parsed_and_errors_become_browser_errors(
        self, tmp_path: Path
    ) -> None:
        chromium = await Chromium.start(profile_dir=tmp_path / "profile", headless=True)
        try:
            tab = await chromium.open_tab()

            assert await tab.evaluate("1 + 1", TypeAdapter(int)) == 2
            with pytest.raises(BrowserError, match="Unexpected value"):
                await tab.evaluate("'two'", TypeAdapter(int))
            with pytest.raises(BrowserError, match="Reading the page failed"):
                await tab.evaluate("throw new Error('boom')", TypeAdapter(int))
        finally:
            await chromium.stop()


class TestBrowserFetch:
    async def test_fetch_reads_main_text_structured_data_and_links(
        self, browser_service: BrowserService, web_server_url: str
    ) -> None:
        page = await browser_service.fetch(f"{web_server_url}/restaurant")

        assert page.url == f"{web_server_url}/restaurant"
        assert page.title == "Saperavi"
        assert "adjaruli khachapuri" in page.text
        assert page.structured_data == (
            {
                "@context": "https://schema.org",
                "@type": "Restaurant",
                "name": "Saperavi",
                "servesCuisine": "Georgian",
                "address": {"streetAddress": "245 E 14th St"},
            },
        )
        assert Link("Menu", f"{web_server_url}/menu") in page.links
        assert all(link.url.startswith("http") for link in page.links)

    async def test_fetch_follows_redirects(
        self, browser_service: BrowserService, web_server_url: str
    ) -> None:
        page = await browser_service.fetch(f"{web_server_url}/redirect")

        assert page.url == f"{web_server_url}/restaurant"

    async def test_fetch_waits_for_scripted_content(
        self, browser_service: BrowserService, web_server_url: str
    ) -> None:
        page = await browser_service.fetch(f"{web_server_url}/scripted")

        assert page.title == "Rendered"
        assert "chakapuli" in page.text

    async def test_fetch_times_out(
        self, browser_config: BrowserConfig, web_server_url: str
    ) -> None:
        service = BrowserService(
            dataclasses.replace(browser_config, page_timeout=timedelta(seconds=1))
        )
        try:
            with pytest.raises(BrowserError, match="Timed out"):
                await service.fetch(f"{web_server_url}/slow")
        finally:
            await service.close()

    @pytest.mark.parametrize(
        "browser_script",
        [
            pytest.param("exit 1", id="exits-immediately"),
            pytest.param(
                'if [ "$1" = --version ]; then echo "Chromium 1.0"; fi; exit 1',
                id="starts-then-dies",
            ),
        ],
    )
    async def test_browser_failures_surface_as_browser_errors(
        self,
        browser_config: BrowserConfig,
        web_server_url: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        browser_script: str,
    ) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        chromium = bin_dir / "chromium"
        chromium.write_text(f"#!/bin/sh\n{browser_script}\n")
        chromium.chmod(0o755)
        monkeypatch.setenv("PATH", str(bin_dir))
        service = BrowserService(browser_config)

        with pytest.raises(BrowserError):
            await service.fetch(f"{web_server_url}/restaurant")

    async def test_browser_reopens_after_closing(
        self, browser_config: BrowserConfig, web_server_url: str
    ) -> None:
        service = BrowserService(
            dataclasses.replace(browser_config, idle_timeout=timedelta(seconds=0.1))
        )
        try:
            await service.fetch(f"{web_server_url}/restaurant")
            await asyncio.sleep(0.5)
            after_idle = await service.fetch(f"{web_server_url}/restaurant")
            await service.close()
            after_close = await service.fetch(f"{web_server_url}/restaurant")
        finally:
            await service.close()

        assert after_idle.title == after_close.title == "Saperavi"


class TestHomeNetworkProtection:
    @pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/", "/x"])
    async def test_refuses_non_web_urls_without_starting_browser(
        self, browser_config: BrowserConfig, url: str
    ) -> None:
        service = BrowserService(browser_config)

        with pytest.raises(BlockedUrlError):
            await service.fetch(url)

        assert not browser_config.profile_dir.exists()

    async def test_refuses_pages_on_private_addresses(
        self, browser_service: BrowserService, home_network_url: str
    ) -> None:
        with pytest.raises(BlockedUrlError, match="not on a public address"):
            await browser_service.fetch(f"{home_network_url}/router")

        assert RecordingHandler.requests == []

    async def test_refuses_redirects_to_private_addresses(
        self,
        browser_service: BrowserService,
        web_server_url: str,
        home_network_url: str,
    ) -> None:
        target = quote(f"{home_network_url}/reboot", safe="")

        with pytest.raises(BlockedUrlError, match="not on a public address"):
            await browser_service.fetch(f"{web_server_url}/redirect-to?url={target}")

        assert RecordingHandler.requests == []

    async def test_blocks_page_resources_on_private_addresses(
        self,
        browser_service: BrowserService,
        web_server_url: str,
        home_network_url: str,
    ) -> None:
        src = quote(f"{home_network_url}/pixel.png", safe="")

        page = await browser_service.fetch(f"{web_server_url}/embed?src={src}")

        assert page.title == "Embeds"
        assert RecordingHandler.requests == []


class TestBrowserSearch:
    async def test_search_returns_results_page(
        self, browser_service: BrowserService
    ) -> None:
        page = await browser_service.search("saperavi")

        assert page.title == "saperavi - Search"
        assert "245 E 14th St" in page.text
        assert Link("Saperavi: Home", "https://www.google.com/goto?url=opaque") in (
            page.links
        )

    async def test_search_raises_when_blocked(
        self, browser_config: BrowserConfig, web_server_url: str
    ) -> None:
        service = BrowserService(
            dataclasses.replace(
                browser_config, google_search_url=f"{web_server_url}/sorry/index"
            )
        )
        try:
            with pytest.raises(SearchBlockedError):
                await service.search("saperavi")
        finally:
            await service.close()
