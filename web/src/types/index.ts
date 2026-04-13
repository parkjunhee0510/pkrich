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
  confidence?: number
  reasoning?: string
}

export interface SignalHistoryEntry {
  date: string
  direction: 'bullish' | 'neutral' | 'bearish'
  catalyst: string
  return_5d?: string
  note?: string
}

export interface SectorComparisonMetric {
  company?: string
  peer_average?: string
  difference?: string
  premium_discount?: string
}

export interface SectorComparison {
  summary?: string
  pe_ratio?: SectorComparisonMetric
  rs_vs_spy?: SectorComparisonMetric
  price_change_30d?: SectorComparisonMetric
}

export interface OptionsSummary {
  expiry?: string
  atm_call_iv?: string
  atm_put_iv?: string
  put_call_ratio?: string
  iv_percentile_30d?: string
}

export interface TradeFrame {
  bull_scenario: string
  base_scenario: string
  bear_scenario: string
  entry_price?: string
  stop_loss?: string
  target_1?: string
  target_2?: string
  risk_reward_ratio?: string
  position_size_note?: string
  invalidation_price: string
  watch_period: string
}

export interface MarketRegimeData {
  regime: 'risk_on' | 'neutral' | 'risk_off'
  confidence: number
  drivers: Record<string, string>
  implication: string
  assessed_at: string
}

export interface TickerDecisionData {
  action: 'buy' | 'watch' | 'avoid'
  conviction: number
  reason: string
  valid_until: string
  factors: Record<string, number>
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
  signal_history?: SignalHistoryEntry[]
  sector_comparison?: SectorComparison
  options_summary?: OptionsSummary
  valuation_score?: ValuationScore
  decision?: TickerDecisionData
}

export interface ValuationScore {
  score: string
  factors: string[]
  assessment: string
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

export interface PortfolioHoldingInput {
  ticker: string
  shares: number
  avg_cost: number
  currency: string
}

export interface LocalPortfolioStatus {
  available: boolean
  stage: 'idle' | 'saved' | 'failed'
  stageLabel: string
  message: string
  updatedAt: string | null
  holdings: PortfolioHoldingInput[]
}

export interface PortfolioSummaryData {
  positions: PortfolioPosition[]
  total_market_value: number
  total_cost_basis: number
  total_unrealized_pnl: number
  total_unrealized_return_pct: number
}

export interface MacroContextVix {
  level: string
  change?: string
  regime?: string
}

export interface MacroEvent {
  type: string
  date: string
  days_until: string
  label: string
  impact?: 'high' | 'medium' | 'low'
}

export interface MacroContext {
  vix?: MacroContextVix
  us10y?: {
    level?: string
    price?: string
    change?: string
  }
  dxy?: {
    level?: string
    price?: string
    change?: string
  }
  copper?: {
    level?: string
    price?: string
    change?: string
  }
  upcoming_macro_events?: MacroEvent[]
}

export interface PortfolioRiskPosition {
  ticker: string
  weight_pct: number
  sector?: string
  market_value: number
  atr_risk_usd: number
}

export interface CorrelationPair {
  ticker_1: string
  ticker_2: string
  correlation: string
  warning: string
}

export interface PortfolioRisk {
  positions_by_weight: PortfolioRiskPosition[]
  sector_exposure?: Record<string, number>
  concentration_warning?: string
  sector_concentration_alerts?: string[]
  correlation_pairs?: CorrelationPair[]
  position_sizing?: Array<{ ticker: string; recommended_shares: string; max_risk_usd: string; stop_distance: string }>
  total_atr_risk_usd?: number
  max_drawdown_2atr_usd?: number
  max_drawdown_2atr_pct?: string
  total_market_value?: number
}

export interface DailyEntry {
  date: string
  market_overview: MarketOverviewEntry[]
  macro_context?: MacroContext | null
  market_regime?: MarketRegimeData | null
  portfolio_risk?: PortfolioRisk | null
  portfolio_summary?: PortfolioSummaryData | null
  tickers: TickerAnalysisData[]
}

export interface WeeklySummaryPreview {
  iso_year: number
  iso_week: number
  start_date: string
  end_date: string
  trading_days: number
  weekly_insight?: string
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
  meta_analysis?: {
    status?: string
    total_evaluated?: number
    by_catalyst_tag?: Record<string, { count: number; avg_return: string; win_rate: string; best: string; worst: string }>
    by_news_tone?: Record<string, { count: number; avg_return: string; win_rate: string; best: string; worst: string }>
    ticker_performance?: Array<{ ticker: string; signals: number; avg_return: string; win_rate: string }>
  }
}

export interface DashboardData {
  days: DailyEntry[]
  signal_stats?: SignalStats
  weekly_summary?: WeeklySummaryPreview
}

export interface BacktestDirectionSummary {
  direction: string
  signals: number
  win_rate: string
  avg_return: string
  cumulative_return: string
  best_return: string
  worst_return: string
}

export interface BacktestEquityPoint {
  date: string
  ticker: string
  signal_direction: string
  strategy_return: string
  equity_multiple: number
  cumulative_return: string
}

export interface BacktestTickerRow {
  ticker: string
  signals: number
  avg_return: string
  win_rate: string
  bull_signals: number
  bear_signals: number
  best_return: string
  worst_return: string
}

export interface BacktestSummary {
  status: string
  strategy?: string
  signals?: number
  win_rate?: string
  avg_return?: string
  cumulative_return?: string
  best_return?: string
  worst_return?: string
  bull?: BacktestDirectionSummary
  bear?: BacktestDirectionSummary
  equity_curve?: BacktestEquityPoint[]
  ticker_rows?: BacktestTickerRow[]
  signal_meta?: {
    meta_analysis?: SignalStats['meta_analysis']
    summary_by_direction?: SignalStats['summary_by_direction']
  }
}

export interface MonthlySummaryData {
  month: string
  status: string
  trading_days?: number
  start_date?: string
  end_date?: string
  top_tickers?: Array<{ ticker: string; avg_daily_change: string }>
  top_sectors?: Array<{ sector: string; avg_daily_change: string }>
}

export interface ChatResponse {
  answer: string
  matched_tickers: string[]
  sources: Array<{ ticker: string; title: string; link: string }>
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  matched_tickers?: string[]
  sources?: Array<{ ticker: string; title: string; link: string }>
}

export interface AnalyticsRun {
  run_date: string
  success: boolean
  daily_api_cost_usd: number
  models_used: Record<string, number>
  llm_usage: Record<string, number>
  batch_count: number
  fallback_count: number
  validation_failure_count: number
}

export interface AnalyticsCostResponse {
  runs: AnalyticsRun[]
  total_cost_usd: number
  average_cost_usd: number
  successful_runs: number
}

export type ApiProviderState = 'used' | 'failed' | 'throttled' | 'unavailable' | 'not_used'

export interface ApiProviderSummary {
  overall_status: 'active' | 'partial' | 'limited' | 'failing' | 'idle'
  used_tickers: number
  throttled_tickers: number
  unavailable_tickers: number
  failed_tickers: number
  not_used_tickers: number
}

export interface ApiStatusSummary {
  run_date: string
  log_path: string
  pipeline_completed: boolean
  providers: Record<string, ApiProviderSummary>
  llm: {
    used: boolean
    planned_batches: number
    completed_batches: number
    failed_batches: number
    validation_failures: number
    estimated_cost_usd: number
    latest_model: string
    models_used: Record<string, number>
  }
}

export interface ApiTickerMatrixRow {
  ticker: string
  name: string
  sector: string
  yfinance: ApiProviderState
  alpha_vantage: ApiProviderState
  polygon: ApiProviderState
  fmp: ApiProviderState
  finnhub: ApiProviderState
  sec_edgar: ApiProviderState
  ir_rss: ApiProviderState
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
  open?: string
  high?: string
  low?: string
  close?: string
  volume?: string
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
