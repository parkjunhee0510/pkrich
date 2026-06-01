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

export interface MacroNarrativeHeadline {
  title: string
  source: string
  url: string
  takeaway: string
}

export interface MacroNarrativeData {
  schema_version?: number
  headline: string
  three_themes: string[]
  risk_map?: string
  what_changed_this_week?: string
  key_headlines?: MacroNarrativeHeadline[]
  source?: 'llm' | 'fallback'
  model?: string
}

export interface TickerDecisionData {
  action: 'buy' | 'watch' | 'avoid'
  conviction: number
  raw_conviction?: number
  reason: string
  valid_until: string
  factors: Record<string, number>
  factor_reasoning?: Record<string, string>
  ensemble_agreement?: 'agree' | 'conflict' | 'single'
  final_consensus?: string
  confidence_meta?: {
    data_quality?: number
    evidence_coverage?: number
    evidence_consistency?: number
    model_agreement?: number
    confidence_gate?: number
    data_quality_score?: number
    data_quality_components?: Record<string, number>
    confidence_penalty?: number
    data_quality_gate?: {
      mode?: 'shadow' | 'enforce' | string
      threshold?: number
      max_action_if_enforced?: 'watch' | string
      would_cap_action?: boolean
    }
    search_evidence_score?: number | null
    search_quality_gate?: {
      mode?: 'shadow' | string
      threshold?: number
      max_action_if_enforced?: 'watch' | string
      would_cap_action?: boolean
      reason?: string
      evidence_count?: number
      source_diversity?: number
    }
  }
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

export interface LocalPortfolioSaveOptions {
  allowTruncate?: boolean
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

export interface PMSwapCandidate {
  held_ticker: string
  candidate_ticker: string
  swap_candidate_score: number
  summary: string
  reasons: string[]
  overlap_context: string
  review_points: string[]
}

export interface PMEventExposureItem {
  ticker: string
  event_risk_score: number
  event_label: string
  event_date: string
  days_until: number
  summary: string
  reasons: string[]
  review_points: string[]
}

export interface PMPriorityQueueItem {
  priority_type: string
  ticker: string
  related_ticker?: string | null
  today_priority_score: number
  summary: string
  reasons: string[]
  destination: string
}

export interface PMViewData {
  as_of: string
  swap_candidates: PMSwapCandidate[]
  event_exposure_items: PMEventExposureItem[]
  today_priority_queue: PMPriorityQueueItem[]
  empty_states: Record<string, string>
}

export interface DailyEntry {
  date: string
  market_overview: MarketOverviewEntry[]
  macro_context?: MacroContext | null
  market_regime?: MarketRegimeData | null
  pm_view?: PMViewData | null
  portfolio_risk?: PortfolioRisk | null
  portfolio_summary?: PortfolioSummaryData | null
  tickers: TickerAnalysisData[]
  state_metadata?: StateMetadata
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

export interface StateMetadata {
  decision_signal_stats_as_of?: string
  decision_signal_stats_includes_current_run?: boolean
  output_signal_stats_as_of?: string
  output_signal_stats_includes_current_run?: boolean
  signal_returns_updated_before_decision?: boolean
}

export interface DashboardData {
  schema_version?: number
  days: DailyEntry[]
  signal_stats?: SignalStats
  weekly_summary?: WeeklySummaryPreview
  state_metadata?: StateMetadata
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

export interface AnalysisPerformanceWindowStats {
  sample_count: number
  completed_count: number
  avg_return: number | null
  median_return: number | null
  win_rate: number | null
  loss_rate: number | null
  directional_win_rate: number | null
  missing_count: number
  return_distribution: {
    positive: number
    negative: number
    flat: number
  }
  triple_barrier_outcomes: Record<string, number>
}

export interface AnalysisPerformanceConvictionBucket {
  sample_count: number
  action_counts: Record<string, number>
  avg_return_1d: number | null
  avg_return_5d: number | null
  avg_return_20d: number | null
  buy_win_rate: number | null
  avoid_win_rate: number | null
}

export interface AiRecommendationWindowStats {
  sample_count: number
  completed_count: number
  avg_return: number | null
  median_return: number | null
  win_rate: number | null
  loss_rate: number | null
  best_return: number | null
  worst_return: number | null
  missing_count: number
}

export interface AiRecommendationConvictionBucket {
  sample_count: number
  action_counts: Record<string, number>
  by_action: Record<string, Record<string, AiRecommendationWindowStats>>
}

export interface AiRecommendationTickerRow {
  ticker: string
  signals: number
  buy_signals: number
  watch_signals: number
  avoid_signals: number
  completed_5d_count: number
  completed_20d_count: number
  avg_return_5d: number | null
  avg_return_20d: number | null
  win_rate_5d: number | null
  win_rate_20d: number | null
}

export interface AiRecommendationExample {
  signal_date: string
  ticker: string
  action: string
  conviction: number | null
  return_5d: number | null
  return_20d: number | null
  catalyst_tag: string
  regime: string
}

export interface AiRecommendationBacktestPayload {
  status: string
  basis: string
  horizons: string[]
  summary: {
    sample_count: number
    completed_20d_count: number
    best_action: string | null
    worst_action: string | null
    notes: string[]
  }
  by_action: Record<string, Record<string, AiRecommendationWindowStats>>
  conviction_buckets: Record<string, AiRecommendationConvictionBucket>
  ticker_leaderboard: AiRecommendationTickerRow[]
  notable_examples: {
    best: AiRecommendationExample[]
    worst: AiRecommendationExample[]
  }
}

export interface AnalysisPerformanceFactorStats {
  sample_count: number
  avg_score: number | null
  positive_score_count: number
  negative_score_count: number
  avg_forward_return_5d: number | null
  avg_forward_return_20d: number | null
  best_action_context?: {
    action: string
    sample_count: number
    avg_return_5d: number | null
  }
  worst_action_context?: {
    action: string
    sample_count: number
    avg_return_5d: number | null
  }
}

export interface AnalysisPerformanceActionChange {
  ticker: string
  previous_action: string
  current_action: string
  previous_conviction: number | null
  current_conviction: number | null
  previous_regime: string
  current_regime: string
  reason_codes: string[]
  summary: string
  contributors: Array<{ factor: string; previous: number | null; current: number | null }>
}

export interface AnalysisPerformancePayload {
  schema_version?: number
  as_of: string
  summary: {
    sample_count: number
    decision_count: number
    completed_return_windows: string[]
    mode: string
    notes: string[]
  }
  signal_performance: Record<string, Record<string, AnalysisPerformanceWindowStats>>
  conviction_calibration?: {
    status: string
    bucket_edges: string[]
    buckets: Record<string, AnalysisPerformanceConvictionBucket>
  }
  regime_performance?: Record<string, Record<string, Record<string, AnalysisPerformanceWindowStats>>>
  factor_attribution?: {
    status: string
    missing_factor_sample_count: number
    factors: Record<string, AnalysisPerformanceFactorStats>
  }
  action_change_reasons?: AnalysisPerformanceActionChange[]
  ai_recommendation_backtest?: AiRecommendationBacktestPayload
}

export interface PerformanceJsonHealth {
  status: string
  invalid_json_count: number
  issues?: Array<{ path: string; error: string }>
}

export interface PerformanceCostSummary {
  total_cost_usd: number
  estimated_monthly_cost_usd: number
  monthly_budget_usd: number
  budget_usage_ratio: number
  llm_calls: number
  ticker_count_for_rate: number
  llm_calls_per_ticker: number
  deep_selected_count: number
  routing_conflicted_count: number
  budget_guard_would_block_count: number
  budget_guard_blocked_count: number
}

export interface PerformanceQualitySummary {
  validated_ticker_count: number
  validation_failure_count: number
  validation_failure_rate: number
  hallucination_warning_count: number
  hallucination_ratio: number
  fact_warning_count: number
  consistency_warning_count: number
}

export interface PerformanceEvidenceSummary {
  provider: string
  ticker_count: number
  covered_ticker_count: number
  coverage_ratio: number
  average_coverage_score: number
  average_freshness_score: number
  candidate_ticker_count: number
  searched_ticker_count: number
  cache_ttl_hours: number
  cache_hit_count: number
  stale_cache_hit_count: number
  cache_hit_ratio: number
  stale_cache_hit_ratio: number
  average_cache_age_hours: number
  max_cache_age_hours: number
  provider_candidate_count: number
  status_counts: Record<string, number>
  priority_ticker_count: number
  priority_covered_ticker_count: number
  priority_coverage_ratio: number
  priority_status_counts: Record<string, number>
}

export interface PerformanceSignalSummary {
  turnover_status: string
  avg_turnover: number
  kelly_status: string
}

export interface PerformanceBaselinePayload {
  schema_version?: number
  as_of: string
  status: string
  latest_run_date: string
  monthly_budget_usd: number
  json_health: PerformanceJsonHealth
  cost: PerformanceCostSummary
  quality: PerformanceQualitySummary
  evidence: PerformanceEvidenceSummary
  signals: PerformanceSignalSummary
}

export interface PerformanceTrendRun {
  run_date: string
  success: boolean
  total_cost_usd: number
  llm_calls: number
  hallucination_ratio: number
  validation_failure_count: number
  deep_selected_count: number
  budget_guard_would_block_count: number
}

export interface PerformanceTrendsPayload {
  schema_version?: number
  as_of: string
  monthly_budget_usd: number
  runs: PerformanceTrendRun[]
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
    selected_tickers?: string[]
    skipped_due_to_priority?: string[]
    router_budget_estimate?: {
      selected_count?: number
      estimated_incremental_cost_usd?: number
      estimated_monthly_cost_usd?: number
    }
    tickers: Array<{
      ticker: string
      selected_for_deep: boolean
      reason?: string
      in_portfolio?: boolean
      conviction?: number
      action?: string
      router_priority_score?: number
      router_reason_codes?: string[]
      skipped_due_to_priority?: boolean
    }>
  }
}

export interface SearchEvidenceTickerSummary {
  coverage_score?: number
  source_diversity?: number
  freshness_score?: number
  evidence_count?: number
  average_relevance_score?: number
  top_domains?: string[]
  evidence_status?: string
  provider_status?: string
  priority_for_refresh?: boolean
  priority_refresh_reasons?: string[]
  cache_source_date?: string
  cache_age_hours?: number
}

export interface SearchEvidenceRunSummary {
  candidate_ticker_count?: number
  searched_ticker_count?: number
  cache_hit_count?: number
  cache_error_count?: number
  stale_cache_hit_count?: number
  cache_ttl_hours?: number
  provider_call_count?: number
  provider_error_count?: number
  priority_tickers?: string[]
  priority_ticker_count?: number
  priority_refresh_reasons?: Record<string, number>
  priority_status_counts?: Record<string, number>
  priority_refresh_candidate_count?: number
  provider_candidate_count?: number
  skipped_ticker_count?: number
  status_counts?: Record<string, number>
}

export interface SearchEvidencePayload {
  schema_version?: number
  date?: string
  generated_at?: string
  provider?: string
  items?: unknown[]
  by_ticker?: Record<string, SearchEvidenceTickerSummary>
  run_summary?: SearchEvidenceRunSummary
}

export interface QualityReliabilityLoopPayload {
  schema_version?: number
  as_of?: string
  status?: string
  summary?: {
    decision_quality_status?: string
    artifact_reliability_status?: string
    evidence_status?: string
    cost_status?: string
  }
  evidence_quality?: {
    status?: string
    ticker_count?: number
    covered_ticker_count?: number
    coverage_ratio?: number
    priority_ticker_count?: number
    priority_covered_ticker_count?: number
    priority_coverage_ratio?: number
    priority_refresh_reasons?: Record<string, number>
    priority_not_refreshed_count?: number
    priority_no_evidence_count?: number
    provider_issue_status?: string
    operational_issue_count?: number
  }
  warnings?: string[]
}

export type RiskIntelStatus = 'ok' | 'partial' | 'degraded' | 'error'
export type RiskIntelAlertLevel = 'observation' | 'warning' | 'alert'

export interface RiskIntelGeneration {
  run_id: string
  as_of?: string
  generated_at?: string
  scoring_config_version?: string
  confidence_config_version?: string
  source_config_version?: string
}

export interface RiskIntelTickerDetail {
  ticker: string
  exposure_type: 'holding' | 'watchlist' | 'sector' | string
  exposure_label_ko: string
  is_holding: boolean
}

export interface RiskIntelSummaryCard {
  id: string
  alert_level: RiskIntelAlertLevel
  alert_level_label_ko: string
  title_ko: string
  summary_ko: string
  affected_sectors: string[]
  affected_tickers: RiskIntelTickerDetail[]
  evidence_counts: Record<string, number>
  top_evidence_refs: string[]
  rationale_ko: string
  detail_node_id?: string
  score?: number
  raw_score?: number
  score_kind?: string
  cap_value?: number | null
  caps_applied?: string[]
  guardrails_applied?: string[]
}

export interface RiskIntelSummaryPayload {
  schema_version: string
  as_of: string
  status: RiskIntelStatus
  cards: RiskIntelSummaryCard[]
  counts: {
    cards: number
    alert_paths: number
  }
  source_tier_status: Record<string, string>
  empty_states: {
    ko: string
  }
  generation: RiskIntelGeneration
  derived_from_graph_run_id: string
}

export interface RiskIntelGraphNode {
  id: string
  node_type: string
  label?: string
  label_ko?: string
  summary_ko?: string
}

export interface RiskIntelGraphEdge {
  id: string
  source_id: string
  target_id: string
  relationship?: string
  relationship_label_ko?: string
  evidence_type: string
  evidence_label_ko?: string
  confidence: number
  severity_delta: number
  evidence_refs: string[]
  inference_refs: string[]
  explanation_ko: string
}

export interface RiskIntelAlertPath {
  id: string
  canonical_issue_id: string
  target_group_type: string
  target_group_id: string
  alert_level: RiskIntelAlertLevel
  alert_level_label_ko: string
  path_node_ids: string[]
  path_edge_ids: string[]
  affected_sector_ids: string[]
  affected_ticker_ids: string[]
  representative_target_id: string
  raw_score: number
  score: number
  score_kind: string
  cap_value?: number | null
  caps_applied: string[]
  guardrails_applied: string[]
  top_evidence_refs: string[]
  rationale_ko: string
}

export interface RiskIntelHealthWarning {
  code: string
  severity: string
  message_ko: string
  ref_type?: string
  ref_id?: string
}

export interface RiskIntelGraphPayload {
  schema_version: string
  as_of: string
  status: RiskIntelStatus
  generation: RiskIntelGeneration
  nodes: RiskIntelGraphNode[]
  edges: RiskIntelGraphEdge[]
  alert_paths: RiskIntelAlertPath[]
  health_warnings: RiskIntelHealthWarning[]
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


// ─── Policy Impact Analysis (Plan T10) ─────────────────────────────────
// Mirrors src/types.py PolicyEvent / TickerImpact / PolicyImpactReport.

export type PolicyEvent = {
  id: string
  category: string
  headline: string
  summary: string
  raw_excerpt: string
  source_url: string
  source_domain: string
  published_at: string
  confidence: number
  // Plan B (active-events dossier)
  effective_through?: string
  first_seen?: string
  last_seen?: string
  age_days?: number
  decay_weight?: number
}

export type TickerImpactDirection = 'positive' | 'negative' | 'neutral'
export type TickerImpactStrength = 'direct' | 'indirect' | 'neutral'

export type TickerImpact = {
  ticker: string
  direction: TickerImpactDirection
  strength: TickerImpactStrength
  score: number
  confidence: number
  rationale: string
}

export type PolicyImpactReport = {
  date: string
  events: PolicyEvent[]
  impacts_by_event: Record<string, TickerImpact[]>
  impacts_by_ticker: Record<string, TickerImpact[]>
  tailwind_scores: Record<string, number>
  metadata: Record<string, unknown>
}
