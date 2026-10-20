from __future__ import annotations

from framework.browser.errors import BlockedUrlError, BrowserError, SearchBlockedError
from framework.browser.page import Link, Page
from framework.browser.service import (
    BrowserConfig,
    BrowserService,
    browser_lifespan,
    get_browser_service,
)

__all__ = [
    "BlockedUrlError",
    "BrowserConfig",
    "BrowserError",
    "BrowserService",
    "Link",
    "Page",
    "SearchBlockedError",
    "browser_lifespan",
    "get_browser_service",
]
