from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WatchlistItem:
    ticker: str
    name: str
    sector: str = ''
    keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    cik: str = ''
    ir_rss_feeds: list[str] = field(default_factory=list)
    ir_source_names: dict[str, str] = field(default_factory=dict)
    sec_filing_tag_priority: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    published_at: str = ''
    link: str = ''


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
    eps: str = 'N/A'
    week52_high: str = 'N/A'
    week52_low: str = 'N/A'
    sma_50: str = 'N/A'
    sma_200: str = 'N/A'
    volume: str = 'N/A'
    avg_volume_3m: str = 'N/A'
    price_to_book: str = 'N/A'
    dividend_yield: str = 'N/A'
    quarterly_financials: list[dict[str, str]] = field(default_factory=list)
    upcoming_events: list[dict[str, str]] = field(default_factory=list)
    price_change_7d: str = 'N/A'
    price_change_30d: str = 'N/A'


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
    fundamentals: dict[str, str] = field(default_factory=dict)
    quarterly_financials: list[dict[str, str]] = field(default_factory=list)
    upcoming_events: list[dict[str, str]] = field(default_factory=list)
    news_tone: dict[str, str | float] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioHolding:
    ticker: str
    shares: float
    avg_cost: float
    currency: str = 'USD'


@dataclass(frozen=True)
class PortfolioPosition:
    ticker: str
    shares: float
    avg_cost: float
    currency: str
    market_price: float | None
    market_value: float | None
    cost_basis: float
    unrealized_pnl: float | None
    unrealized_return_pct: float | None


@dataclass(frozen=True)
class PortfolioSummary:
    positions: list[PortfolioPosition] = field(default_factory=list)
    total_market_value: float | None = None
    total_cost_basis: float = 0.0
    total_unrealized_pnl: float | None = None
    total_unrealized_return_pct: float | None = None
