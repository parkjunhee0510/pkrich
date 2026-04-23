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
  rs_vs_sector_etf: string
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

export interface EarningsPattern {
  beat_streak: number
  surprise_trend: 'improving' | 'deteriorating' | 'stable' | 'insufficient_data'
  avg_surprise_pct: string
  quarters_analyzed: number
  pattern_note: string
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
  tone?: 'bullish' | 'neutral' | 'bearish' | string
  unusual_activity?: string
  oi_change?: string
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
  regime: 'risk_on' | 'neutral' | 'risk_off' | 'reflation' | 'defensive_bias'
  confidence: number
  drivers: Record<string, string>
  implication: string
  assessed_at: string
  sub_regime?: string
  forward_signals?: Record<string, string>
}

export interface MacroNarrativeData {
  headline: string
  three_themes: string[]
  risk_map?: string
  what_changed_this_week?: string
  source?: 'llm' | 'fallback'
  model?: string
}

export interface TickerDecisionData {
  action: 'buy' | 'watch' | 'avoid'
  conviction: number
  reason: string
  valid_until: string
  factors: Record<string, number>
  factor_reasoning?: Record<string, string>
  ensemble_agreement?: 'agree' | 'conflict' | 'single'
}

export interface AnalysisConsensusData {
  status?: 'agreed' | 'conflicted' | 'not_applicable' | string
  economy_action?: string
  economy_reason?: string
  deep_action?: string
  deep_reason?: string
  direction_agreement?: boolean | null
  selection_reason?: string
}

export interface CommitteeRoleData {
  role?: string
  round?: string
  profile?: string
  stance?: string
  action?: string
  confidence?: number
  strong_objection?: boolean
  summary?: string
  valid?: boolean
  invalid_reason?: string
}

export interface CommitteeAnalysisData {
  status?: string
  agreement_status?: string
  deep_review_triggered?: boolean
  deep_review_reasons?: string[]
  roles?: Record<string, CommitteeRoleData>
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
  earnings_pattern?: EarningsPattern
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
  analysis_consensus?: AnalysisConsensusData
  committee_analysis?: CommitteeAnalysisData
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
  event_type?: string
  event_code?: string
  category?: string
  date: string
  days_until: string
  label: string
  severity?: 'high' | 'medium' | 'low' | string
  region?: string
  transmission_channels?: string[]
  affected_sectors?: string[]
  affected_industries?: string[]
  direction?: string
  summary_ko?: string
  expires_at?: string
  impact?: 'high' | 'medium' | 'low'
  source?: string
  actual?: string
  consensus?: string
  previous?: string
  surprise_direction?: string
  market_bias?: string
  description?: string
  sensitivity_tags?: string | string[]
  sensitive_holdings?: SensitiveHolding[]
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
  macro_events?: MacroEvent[]
  portfolio_event_sensitivity?: PortfolioMacroSensitivity[]
  ticker_macro_sensitivity?: Record<string, Array<{ event_code: string; label: string; date: string; sensitivity: string; reason: string }>>
  portfolio_sensitivity_summary?: string
  yield_curve_10y_2y?: { level?: string; spread_bps?: string; status?: string }
  yield_curve_10y_3m?: { level?: string; spread_bps?: string; status?: string }
  credit_spread?: { level?: string; hy_level?: string; ig_level?: string }
  surprise_score?: {
    growth?: { score: number; samples: number }
    inflation?: { score: number; samples: number }
    labor?: { score: number; samples: number }
    composite?: number
    confidence?: 'high' | 'medium' | 'low'
    window_days?: number
  }
  oil_wti?: { level?: string; price?: string; change?: string }
  gold?: { level?: string; price?: string; change?: string }
  hyg?: { level?: string; price?: string; change?: string }
  lqd?: { level?: string; price?: string; change?: string }
  macro_narrative?: MacroNarrativeData
  ticker_macro_betas?: Record<string, {
    rates_beta?: number
    usd_beta?: number
    oil_beta?: number
    credit_beta?: number
    source?: string
    r2?: number | null
    samples?: number
    snapshot?: string
  }>
}

export interface SensitiveHolding {
  ticker: string
  name: string
  sector: string
  sensitivity: 'high' | 'medium' | 'low'
  reason: string
}

export interface PortfolioMacroSensitivity extends MacroEvent {
  sensitive_holdings?: SensitiveHolding[]
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
  correlation_matrix?: Record<string, Record<string, number | null>>
  position_sizing?: Array<{ ticker: string; recommended_shares: string; max_risk_usd: string; stop_distance: string }>
  total_atr_risk_usd?: number
  max_drawdown_2atr_usd?: number
  max_drawdown_2atr_pct?: string
  total_market_value?: number
  hhi?: number
  portfolio_beta?: number | null
  mdd_20d?: number | null
  mdd_20d_series?: Array<{ date: string; drawdown_pct: number }>
  var_95?: number | null
  risk_grade?: 'A' | 'B' | 'C' | 'D' | string
  recommendations?: string[]
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

export interface WeeklyReportSection {
  summary?: string
  details?: string[]
  items?: Array<
    | string
    | {
        ticker?: string
        name?: string
        weekly_change?: string
        catalyst?: string
        decision_change?: string
      }
  >
}

export interface WeeklyReport {
  headline?: string
  summary?: string
  market_environment?: WeeklyReportSection
  top_movers?: WeeklyReportSection
  signal_review?: WeeklyReportSection
  risk_points?: WeeklyReportSection
  next_week_action_plan?: WeeklyReportSection
  portfolio_suggestions?: WeeklyReportSection
}

export interface WeeklySummaryPreview {
  iso_year: number
  iso_week: number
  start_date: string
  end_date: string
  trading_days: number
  weekly_insight?: string
  weekly_report?: WeeklyReport
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
  schema_version?: number
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
  message?: string
  first_eval_date?: string
  pending_signals?: number
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
  cost_log?: CostLogPayload
}

export interface CostLogRunProfile {
  cost_usd: number
  tokens: number
  calls: number
  models: Record<string, number>
}

export interface CostLogRun {
  run_date: string
  success: boolean
  total_cost_usd: number
  profiles: Record<string, CostLogRunProfile>
  routing: {
    ensemble_enabled: boolean
    eligible_count: number
    selected_count: number
    skipped_due_to_cap_count: number
    conflicted_count: number
  }
  deep_pass_value: {
    deep_cost_usd: number
    selected_ticker_count: number
    cost_per_selected_ticker_usd: number
    share_of_total_cost: number
    worth_it_hint: string
  }
}

export interface CostLogPayload {
  schema_version?: number
  runs: CostLogRun[]
  latest?: CostLogRun
}

export interface AnalysisQualityRun {
  run_date: string
  success: boolean
  daily_api_cost_usd: number
  batch_count: number
  validated_ticker_count: number
  validation_failure_count: number
  schema_violation_count: number
  fact_warning_count: number
  consistency_warning_count: number
  hallucination_warning_count: number
  hallucination_ratio: number
}

export interface AnalysisQualityPayload {
  runs: AnalysisQualityRun[]
  latest?: AnalysisQualityRun
}

export interface DirectionAlignmentPair {
  rule_direction: string
  llm_direction: string
  count: number
}

export interface DirectionAlignmentConflict {
  signal_date: string
  ticker: string
  signal_direction: string
  llm_direction: string
  catalyst_tag?: string
  conviction?: string
  action?: string
  regime?: string
}

export interface DirectionAlignmentPayload {
  schema_version?: number
  summary: {
    total_signals: number
    comparable_signals: number
    agreement_count: number
    conflict_count: number
    agreement_rate: number | null
    latest_signal_date?: string
  }
  by_pair: DirectionAlignmentPair[]
  recent_conflicts: DirectionAlignmentConflict[]
}

export interface RoutingOutcomePayload {
  schema_version?: number
  run_count: number
  evaluated_signals: number
  latest_run_date?: string
  status?: string
  summary: {
    deep_selected_count: number
    economy_only_count: number
    portfolio_priority_count: number
    deep_selected_avg_return_20d: number | null
    economy_only_avg_return_20d: number | null
    portfolio_priority_avg_return_20d: number | null
    deep_selected_hit_rate: number | null
    economy_only_hit_rate: number | null
    portfolio_priority_hit_rate: number | null
    avg_return_delta_20d: number | null
    hit_rate_delta: number | null
  }
  periods: Array<{
    period: string
    deep_selected_count: number
    economy_only_count: number
    portfolio_priority_count: number
    deep_selected_avg_return_20d: number | null
    economy_only_avg_return_20d: number | null
    portfolio_priority_avg_return_20d: number | null
    deep_selected_hit_rate: number | null
    economy_only_hit_rate: number | null
    portfolio_priority_hit_rate: number | null
    avg_return_delta_20d: number | null
    hit_rate_delta: number | null
  }>
  latest_run?: {
    run_date: string
    trigger_range: [number, number]
    max_daily_ensemble: number
    portfolio_priority: boolean
    deep_pass_count: number
    tickers: Array<{
      ticker: string
      selected_for_deep: boolean
      reason?: string
      in_portfolio?: boolean
      conviction?: number
      action?: string
    }>
  }
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
    quality?: {
      run_date?: string
      validated_ticker_count?: number
      validation_failure_count?: number
      schema_violation_count?: number
      fact_warning_count?: number
      consistency_warning_count?: number
      hallucination_warning_count?: number
      hallucination_ratio?: number
    }
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
