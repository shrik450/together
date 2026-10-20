"""Reading Google's results page.

Google's markup changes constantly, so results are not scraped from specific
elements. The model gets the page's text, which includes Google's own panels
such as a place's address and hours, plus the result links found here.
"""

from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import parse_qs, urlsplit

from framework.browser.page import Link


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


def _result_url(url: str) -> str | None:
    parts = urlsplit(url)
    if not _is_google_host(parts.hostname or ""):
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


def _is_google_host(hostname: str) -> bool:
    return "google" in hostname.split(".") or hostname.endswith(
        (".gstatic.com", ".googleusercontent.com")
    )
