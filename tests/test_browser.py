from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from framework.browser import (
    BlockedUrlError,
    BrowserConfig,
    BrowserError,
    BrowserService,
    Link,
    SearchBlockedError,
)
from framework.browser.service import (
    is_public_address,
    is_search_blocked,
    parse_json_ld,
    search_result_links,
)


class TestAddressChecks:
    @pytest.mark.parametrize(
        ("address", "public"),
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
    def test_is_public_address(self, address: str, public: bool) -> None:
        assert is_public_address(address) is public

    @pytest.mark.parametrize(
        "url",
        ["http://127.0.0.1/", "http://localhost:8000/", "file:///etc/passwd", "/x"],
    )
    async def test_refuses_non_public_urls_without_starting_browser(
        self, tmp_path: Path, url: str
    ) -> None:
        service = BrowserService(BrowserConfig(profile_dir=tmp_path / "profile"))

        with pytest.raises(BlockedUrlError):
            await service.fetch(url)

        assert not (tmp_path / "profile").exists()


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

    async def test_fetch_times_out(self, tmp_path: Path, web_server_url: str) -> None:
        service = BrowserService(
            BrowserConfig(
                profile_dir=tmp_path / "profile",
                allow_private_networks=True,
                page_timeout=timedelta(seconds=1),
            )
        )
        try:
            with pytest.raises(BrowserError, match="Timed out"):
                await service.fetch(f"{web_server_url}/slow")
        finally:
            await service.close()

    async def test_browser_closes_when_idle_and_restarts_on_use(
        self, tmp_path: Path, web_server_url: str
    ) -> None:
        service = BrowserService(
            BrowserConfig(
                profile_dir=tmp_path / "profile",
                allow_private_networks=True,
                idle_timeout=timedelta(seconds=0.2),
            )
        )
        try:
            await service.fetch(f"{web_server_url}/restaurant")
            assert service._browser is not None
            assert service._idle_close is not None
            await service._idle_close
            assert service._browser is None

            page = await service.fetch(f"{web_server_url}/restaurant")
            assert page.title == "Saperavi"
        finally:
            await service.close()


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
        self, tmp_path: Path, web_server_url: str
    ) -> None:
        service = BrowserService(
            BrowserConfig(
                profile_dir=tmp_path / "profile",
                allow_private_networks=True,
                search_url=f"{web_server_url}/sorry/index",
            )
        )
        try:
            with pytest.raises(SearchBlockedError):
                await service.search("saperavi")
        finally:
            await service.close()
