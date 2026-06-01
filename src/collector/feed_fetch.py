"""Bounded, scheme-validated RSS/Atom feed fetching.

``feedparser.parse(url)`` has no timeout and will happily follow any scheme
(``file://``, ``ftp://`` …), so a single slow or hostile feed can hang the
whole daily run or read a local file. This helper:

  * rejects non-``http(s)`` URLs before any I/O (SSRF guard), and
  * fetches the bytes with a PER-CALL socket timeout — thread-safe, unlike
    ``socket.setdefaulttimeout`` — before handing them to feedparser.

On a rejected scheme or any fetch error it returns an empty parse
(``feed.entries == []``), so callers that already iterate
``getattr(feed, "entries", [])`` degrade gracefully (that feed simply
contributes no items, exactly as a previously-failing feed would).
"""
from __future__ import annotations

from typing import Any
from urllib import request
from urllib.error import URLError

# A descriptive UA — some feed hosts reject the bare urllib default.
_FEED_USER_AGENT = "pkrich-stock-research/1.0 (RSS reader)"

# Default per-request timeout (seconds). Generous enough for slow feeds, but
# bounded so one unresponsive host cannot stall the pipeline.
DEFAULT_FEED_TIMEOUT = 10.0


def parse_feed(url: str, *, timeout: float = DEFAULT_FEED_TIMEOUT) -> Any:
    """Fetch and parse ``url`` with a bounded timeout and an ``http(s)`` guard.

    Returns a feedparser result. The bytes are fetched here (not by feedparser)
    so the timeout actually applies; feedparser then parses the in-memory bytes.
    """
    import feedparser  # type: ignore  # lazy: optional dependency

    if not isinstance(url, str) or not url.lower().startswith(("http://", "https://")):
        return feedparser.parse(b"")
    try:
        req = request.Request(url, headers={"User-Agent": _FEED_USER_AGENT})
        with request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — scheme validated above
            content = resp.read()
    except (URLError, OSError, ValueError):
        return feedparser.parse(b"")
    return feedparser.parse(content)
