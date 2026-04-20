"""Concrete NewsProvider implementations.

This subpackage mirrors the structure of `src/collector/providers/`, but
for the news subsystem (see `src/collector/news_base.py`). Each provider
here is a thin adapter over the existing legacy collectors in
`src/collector/news_rss.py`, `src/collector/news_search.py`,
`src/collector/sec_edgar.py`, and `src/collector/ir_rss.py` — keeping the
migration non-destructive. Cutover happens in Step 5.

Providers currently available:
  * SECEdgarNewsProvider    — source_priority 4 (primary)
  * IRRSSNewsProvider       — source_priority 2 (primary corporate)
  * GoogleNewsNewsProvider  — source_priority 1 (aggregator, 6 feeds)
  * DuckDuckGoNewsProvider  — source_priority 0 (supplemental)
"""
from __future__ import annotations

from src.collector.providers.news.duckduckgo_news_provider import DuckDuckGoNewsProvider
from src.collector.providers.news.google_news_news_provider import GoogleNewsNewsProvider
from src.collector.providers.news.ir_rss_news_provider import IRRSSNewsProvider
from src.collector.providers.news.sec_edgar_news_provider import SECEdgarNewsProvider

__all__ = [
    "DuckDuckGoNewsProvider",
    "GoogleNewsNewsProvider",
    "IRRSSNewsProvider",
    "SECEdgarNewsProvider",
]
