export interface MarketOverviewEntry {
  label: string
  symbol: string
  price: string
  change: string
}

export interface NewsReference {
  title: string
  source: string
  published_at: string
  link: string
}

export interface SecFilingReference {
  tag: string
  title: string
  form_type: string
  item_number?: string
  catalyst_type?: 'hard' | 'medium' | 'soft'
  importance_score?: number
  published_at: string
  link: string
  source: string
}

export interface UpcomingEvent {
  type: string
  label: string
  date: string
  days_until: string
  timing?: string
}

export interface QuarterlyFinancialRow {
  quarter: string
  revenue: string
  operating_income: string
  eps: string
  estimated_eps?: string
  surprise_pct?: string
  beat_miss?: 'beat' | 'miss' | 'in-line' | 'N/A'
}

export interface PriceAction {
  atr_14d: string
  atr_percent: string
  relative_volume: string
  gap_percent: string
  price_vs_sma50: string
  price_vs_sma200: string
  week52_position: string
  rs_vs_spy: string
}

export interface EarningsSetup {
  forward_eps: string
  ttm_eps: string
  forward_vs_ttm: string
  earnings_growth: string
  latest_estimated_eps: string
  latest_surprise_pct: string
  latest_beat_miss: 'beat' | 'miss' | 'in-line' | 'N/A'
  next_earnings_event: string
}

export interface NewsTone {
  label: 'bullish' | 'neutral' | 'bearish'
  score: number
}

export interface TradeFrame {
  bull_scenario: string
  base_scenario: string
  bear_scenario: string
  invalidation_price: string
  watch_period: string
}

export interface TickerAnalysisData {
  ticker: string
  name: string
  date: string
  summary: string
  key_news: string[]
  news_references: NewsReference[]
  financial_highlights: string[]
  risks_or_watchpoints: string[]
  signal_or_takeaway: string
  data_snapshot: Record<string, string>
  fundamentals: Record<string, string>
  earnings_setup: EarningsSetup
  price_action: PriceAction
  quarterly_financials: QuarterlyFinancialRow[]
  upcoming_events: UpcomingEvent[]
  news_tone: NewsTone
  trade_frame: TradeFrame
  period_changes: Record<string, string>
  sec_filing_tags: string[]
  sec_filings: SecFilingReference[]
}

export interface PortfolioPosition {
  ticker: string
  shares: number
  avg_cost: number
  currency: string
  market_price: number
  market_value: number
  cost_basis: number
  unrealized_pnl: number
  unrealized_return_pct: number
}

export interface PortfolioSummaryData {
  positions: PortfolioPosition[]
  total_market_value: number
  total_cost_basis: number
  total_unrealized_pnl: number
  total_unrealized_return_pct: number
}

export interface DailyEntry {
  date: string
  market_overview: MarketOverviewEntry[]
  portfolio_summary?: PortfolioSummaryData | null
  tickers: TickerAnalysisData[]
}

export interface SignalHistoryRow {
  signal_date: string
  ticker: string
  signal_type: string
  signal_direction: 'bull' | 'bear' | 'neutral'
  signal_price: string
  catalyst_tag: string
  news_tone: string
  trade_frame_scenario: string
  return_1d: string
  return_5d: string
  return_20d: string
  evaluated_1d: string
  evaluated_5d: string
  evaluated_20d: string
}

export interface SignalDirectionSummary {
  count: number
  evaluated_5d: number
  win_rate_5d: string
  avg_return_5d: string
}

export interface SignalStats {
  recent_signals: SignalHistoryRow[]
  summary_by_direction: Record<string, SignalDirectionSummary>
}

export interface DashboardData {
  days: DailyEntry[]
  signal_stats?: SignalStats
}

export interface PriceHistoryRow {
  date: string
  ticker: string
  price: string
  daily_change: string
  market_cap: string
  trailing_pe: string
  eps: string
  '52w_high': string
  '52w_low': string
}

export interface TickerTimelineEntry {
  date: string
  price: string
  daily_change: string
  signal_or_takeaway: string
  top_news_summary: string
  top_news_link: string
  news_tone: NewsTone
  upcoming_events: UpcomingEvent[]
}

export type TickerTimelinesData = Record<string, TickerTimelineEntry[]>
