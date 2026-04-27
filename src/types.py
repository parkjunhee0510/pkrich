from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


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
    alert_rules: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    published_at: str = ''
    link: str = ''
    form_type: str = ''
    item_number: str = ''
    catalyst_type: str = ''
    importance_score: int = 0


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
    forward_eps: str = 'N/A'
    earnings_growth: str = 'N/A'
    short_float_pct: str = 'N/A'
    short_ratio: str = 'N/A'
    analyst_target_price: str = 'N/A'
    analyst_recommendation: str = 'N/A'
    analyst_count: str = 'N/A'
    held_by_insiders: str = 'N/A'
    held_by_institutions: str = 'N/A'
    implied_volatility: str = 'N/A'
    quarterly_financials: list[dict[str, str]] = field(default_factory=list)
    upcoming_events: list[dict[str, str]] = field(default_factory=list)
    price_change_7d: str = 'N/A'
    price_change_30d: str = 'N/A'
    atr_14d: str = 'N/A'
    atr_percent: str = 'N/A'
    relative_volume: str = 'N/A'
    gap_percent: str = 'N/A'
    price_vs_sma50: str = 'N/A'
    price_vs_sma200: str = 'N/A'
    week52_position: str = 'N/A'
    rs_vs_spy: str = 'N/A'
    rs_vs_sector_etf: str = 'N/A'
    options_summary: dict[str, str] = field(default_factory=dict)
    open_price: str = 'N/A'
    high_price: str = 'N/A'
    low_price: str = 'N/A'
    close_price: str = 'N/A'
    day_volume: str = 'N/A'
    analyst_estimate_revisions: dict[str, str] = field(default_factory=dict)
    insider_transactions: list[dict[str, str]] = field(default_factory=list)
    institutional_changes: dict[str, str] = field(default_factory=dict)
    fmp_earnings_surprises: list[dict[str, str]] = field(default_factory=list)
    options_flow: dict[str, str] = field(default_factory=dict)
    recommendation_trends: list[dict[str, str]] = field(default_factory=list)
    fundamental_metrics: dict[str, str] = field(default_factory=dict)
    technical_indicators: dict[str, str] = field(default_factory=dict)
    historical_prices: list[dict[str, str]] = field(default_factory=list)


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
    price_action: dict[str, str] = field(default_factory=dict)
    quarterly_financials: list[dict[str, str]] = field(default_factory=list)
    upcoming_events: list[dict[str, str]] = field(default_factory=list)
    news_tone: dict[str, str | float | int] = field(default_factory=dict)
    trade_frame: dict[str, str] = field(default_factory=dict)
    options_summary: dict[str, str] = field(default_factory=dict)
    signal_history: list[dict[str, str]] = field(default_factory=list)
    sector_comparison: dict[str, object] = field(default_factory=dict)
    peer_rank: dict[str, object] = field(default_factory=dict)
    valuation_score: dict[str, object] = field(default_factory=dict)
    analysis_consensus: dict[str, object] = field(default_factory=dict)
    committee_analysis: dict[str, object] = field(default_factory=dict)
    historical_prices: list[dict[str, str]] = field(default_factory=list)


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


@dataclass(frozen=True)
class PortfolioRiskMetrics:
    hhi: float
    portfolio_beta: float | None
    correlation_matrix: dict[str, dict[str, float | None]] = field(default_factory=dict)
    mdd_20d: float | None = None
    var_95: float | None = None
    risk_grade: str = "B"
    recommendations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PeerInfo:
    ticker: str
    sector: str = 'N/A'
    market_cap: str = 'N/A'
    avg_volume: str = 'N/A'
    data_coverage_score: float = 0.0
    pe_ratio: str = 'N/A'
    roe: str = 'N/A'
    gross_margin: str = 'N/A'
    price_change_30d: str = 'N/A'
    rs_vs_spy: str = 'N/A'
    revenue_growth: str = 'N/A'
    dividend_yield: str = 'N/A'


@dataclass(frozen=True)
class MarketRegime:
    regime: Literal['risk_on', 'neutral', 'risk_off', 'reflation', 'defensive_bias'] = 'neutral'
    confidence: int = 0
    drivers: dict[str, str] = field(default_factory=dict)
    implication: str = ''
    assessed_at: str = ''
    sub_regime: str = ''
    forward_signals: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TickerDecision:
    ticker: str = ''
    action: Literal['buy', 'watch', 'avoid'] = 'watch'
    conviction: int = 0
    raw_conviction: int = 0
    reason: str = ''
    valid_until: str = ''
    factors: dict[str, float] = field(default_factory=dict)
    confidence_meta: dict[str, float] = field(default_factory=dict)
    factor_reasoning: dict[str, str] = field(default_factory=dict)
    final_consensus: Literal['single', 'agree', 'resolved', 'conflict'] = 'single'


POLICY_CATEGORIES = (
    'interest_rate', 'antitrust', 'export_control', 'subsidy',
    'tariff', 'ira', 'chips_act', 'fda', 'defense_budget',
    'energy_policy', 'other',
)


@dataclass(frozen=True)
class PolicyEvent:
    id: str
    category: str
    headline: str
    summary: str
    raw_excerpt: str
    source_url: str
    source_domain: str
    published_at: str
    confidence: float


@dataclass(frozen=True)
class TickerImpact:
    ticker: str
    direction: Literal['positive', 'negative', 'neutral']
    strength: Literal['direct', 'indirect', 'neutral']
    score: float
    confidence: float
    rationale: str


@dataclass(frozen=True)
class PolicyImpactReport:
    date: str
    events: list = field(default_factory=list)
    impacts_by_event: dict = field(default_factory=dict)
    impacts_by_ticker: dict = field(default_factory=dict)
    tailwind_scores: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
