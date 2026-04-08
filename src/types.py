from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WatchlistItem:
    ticker: str
    name: str
    sector: str = ""
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    published_at: str = ""
    link: str = ""


@dataclass(frozen=True)
class CollectedTickerData:
    ticker: str
    name: str
    sector: str
    price: float | None
    change_percent: float | None
    currency: str
    market_cap: str
    pe_ratio: str
    summary_note: str


@dataclass(frozen=True)
class TickerAnalysis:
    ticker: str
    name: str
    date: str
    summary: str
    key_news: list[str]
    news_references: list[NewsItem]
    financial_highlights: list[str]
    risks_or_watchpoints: list[str]
    signal_or_takeaway: str
    data_snapshot: dict[str, str]
