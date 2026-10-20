from __future__ import annotations

import html
import time
from collections.abc import Mapping, Sequence
from http.server import BaseHTTPRequestHandler
from typing import Any, ClassVar, override
from urllib.parse import parse_qs, urlsplit

_scheduler_task_calls: list[dict[str, Any]] = []


def reset_scheduler_task_calls() -> None:
    _scheduler_task_calls.clear()


def get_scheduler_task_calls() -> Sequence[Mapping[str, Any]]:
    return tuple(_scheduler_task_calls)


def scheduler_test_task(*args: object, **kwargs: object) -> dict[str, Any]:
    payload = {"args": tuple(args), "kwargs": dict(kwargs)}
    _scheduler_task_calls.append(payload)
    return payload


def scheduler_other_task(label: str = "other") -> str:
    _scheduler_task_calls.append({"args": (label,), "kwargs": {}})
    return label


RESTAURANT_PAGE = """<!doctype html>
<html>
<head>
<title>Saperavi</title>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Restaurant", "name": "Saperavi",
 "servesCuisine": "Georgian", "address": {"streetAddress": "245 E 14th St"}}
</script>
<script type="application/ld+json">{not json</script>
</head>
<body>
<nav><a href="/menu">Menu</a> <a href="mailto:hi@example.com">Email</a></nav>
<article>
<h1>Saperavi</h1>
<p>Georgian food in the East Village. Our adjaruli khachapuri is baked to order
with sulguni cheese, butter and a soft egg yolk, and our khinkali are folded by
hand every morning. We have been serving the neighbourhood since 2019 and we
look forward to welcoming you for dinner, brunch on weekends, or a glass of
Saperavi wine at the bar.</p>
<p>Reservations are recommended for groups of six or more.</p>
</article>
</body>
</html>
"""

SCRIPTED_PAGE = """<!doctype html>
<html><head><title>Loading</title></head>
<body><div id="app"></div>
<script>
setTimeout(() => {
  document.title = "Rendered";
  document.getElementById("app").innerText = "Today's special: chakapuli";
}, 300);
</script>
</body></html>
"""

SEARCH_PAGE = """<!doctype html>
<html><head><title>{query} - Search</title></head>
<body>
<div>Saperavi 4.9 Georgian 245 E 14th St</div>
<a href="https://www.google.com/goto?url=opaque">Saperavi: Home</a>
<a href="https://www.google.com/goto?url=opaque2">Read more</a>
<a href="https://www.google.com/url?q=https://example.com/review">A review</a>
<a href="https://www.google.com/search?q=images">Images</a>
<a href="https://saperavinyc.com/">Saperavi site</a>
</body></html>
"""


EMBED_PAGE = """<!doctype html>
<html><head><title>Embeds</title></head>
<body><p>A page with an image from elsewhere.</p><img src="{src}"></body></html>
"""


class WebFixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        if parts.path == "/restaurant":
            self._send_html(RESTAURANT_PAGE)
        elif parts.path == "/scripted":
            self._send_html(SCRIPTED_PAGE)
        elif parts.path == "/redirect":
            self._redirect("/restaurant")
        elif parts.path == "/redirect-to":
            self._redirect(parse_qs(parts.query)["url"][0])
        elif parts.path == "/embed":
            src = html.escape(parse_qs(parts.query)["src"][0])
            self._send_html(EMBED_PAGE.format(src=src))
        elif parts.path == "/search":
            query = parse_qs(parts.query).get("q", [""])[0]
            self._send_html(SEARCH_PAGE.format(query=html.escape(query)))
        elif parts.path == "/sorry/index":
            self._send_html("<html><body>Unusual traffic</body></html>")
        elif parts.path == "/slow":
            time.sleep(3)
            self._send_html("<html><body>Too late</body></html>")
        else:
            self.send_error(404)

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _send_html(self, body: str) -> None:
        encoded = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @override
    def log_message(self, format: str, *args: Any) -> None:
        return


class RecordingHandler(BaseHTTPRequestHandler):
    """Stands in for a device on the home network and records every request."""

    requests: ClassVar[list[str]] = []

    def do_GET(self) -> None:
        self.requests.append(self.path)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    @override
    def log_message(self, format: str, *args: Any) -> None:
        return
