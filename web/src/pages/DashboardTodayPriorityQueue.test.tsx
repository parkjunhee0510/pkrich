import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type {
  DashboardData,
  QualityReliabilityLoopPayload,
  RiskIntelSummaryPayload,
  SearchEvidencePayload,
  TickerAnalysisData,
} from '../types'
import { Dashboard } from './Dashboard'

const dashboardData: DashboardData = {
  days: [
    {
      date: '2026-05-20',
      market_overview: [],
      macro_context: null,
      market_regime: null,
      tickers: [
        buildTicker({
          ticker: 'AMD',
          name: 'Advanced Micro Devices',
          action: 'watch',
          conviction: 58,
          sector: 'Semiconductors',
        }),
      ],
    },
    {
      date: '2026-05-21',
      market_overview: [],
      macro_context: null,
      market_regime: null,
      tickers: [
        buildTicker({
          ticker: 'AMD',
          name: 'Advanced Micro Devices',
          action: 'buy',
          conviction: 76,
          sector: 'Semiconductors',
          newsTone: 'bullish',
          relativeVolume: '1.8',
          rsVsSpy: '+3.2%',
          rsVsSector: '+1.1%',
        }),
        buildTicker({
          ticker: 'KO',
          name: 'Coca-Cola',
          action: 'watch',
          conviction: 42,
          sector: 'Consumer Staples',
        }),
      ],
    },
  ],
}

const searchEvidence: SearchEvidencePayload = {
  schema_version: 1,
  date: '2026-05-21',
  by_ticker: {
    AMD: {
      evidence_status: 'covered',
      provider_status: 'skipped',
      priority_for_refresh: true,
      priority_refresh_reasons: ['router_selected', 'not_refreshed'],
      evidence_count: 2,
      cache_age_hours: 36,
    },
    KO: {
      evidence_status: 'covered',
      provider_status: 'cache_hit',
      priority_for_refresh: false,
      priority_refresh_reasons: [],
      evidence_count: 1,
      cache_age_hours: 4,
    },
  },
  run_summary: {
    cache_ttl_hours: 24,
    priority_tickers: ['AMD'],
    priority_ticker_count: 1,
  },
}

const qualityLoop: QualityReliabilityLoopPayload = {
  schema_version: 1,
  as_of: '2026-05-21',
  evidence_quality: {
    coverage_ratio: 0,
  },
  warnings: ['priority_evidence_not_refreshed'],
}

const riskIntelSummary: RiskIntelSummaryPayload = {
  schema_version: '1.0.0',
  as_of: '2026-05-21',
  status: 'ok',
  cards: [
    {
      id: 'risk-amd-supply',
      alert_level: 'alert',
      alert_level_label_ko: '경보',
      title_ko: 'AMD 공급망 경보',
      summary_ko: 'AMD 관련 공급망 리스크가 관찰됩니다.',
      affected_sectors: ['Semiconductors'],
      affected_tickers: [
        {
          ticker: 'AMD',
          exposure_type: 'watchlist',
          exposure_label_ko: '관심 종목',
          is_holding: false,
        },
      ],
      evidence_counts: {},
      top_evidence_refs: [],
      rationale_ko: 'AMD 리스크 인텔 카드입니다.',
    },
  ],
  counts: {
    cards: 1,
    alert_paths: 1,
  },
  source_tier_status: {},
  empty_states: {
    ko: '',
  },
  generation: {
    run_id: 'risk-run-2026-05-21',
  },
  derived_from_graph_run_id: 'risk-run-2026-05-21',
}

vi.mock('../hooks/useDashboardData', () => ({
  useDashboardData: () => ({
    data: dashboardData,
    loading: false,
    refreshing: false,
    error: null,
    refresh: vi.fn(),
  }),
}))

vi.mock('../hooks/useSearchEvidenceData', () => ({
  useSearchEvidenceData: () => ({ searchEvidence, loading: false, error: null }),
}))

vi.mock('../hooks/useQualityReliabilityLoopData', () => ({
  useQualityReliabilityLoopData: () => ({ qualityLoop, loading: false, error: null }),
}))

vi.mock('../hooks/useRiskIntelData', () => ({
  useRiskIntelData: () => ({
    summary: riskIntelSummary,
    graph: null,
    loading: false,
    error: null,
    graphError: null,
  }),
}))

vi.mock('../components/TraderDashboardPanels', () => ({
  TodaySetupBoard: () => <div data-testid="today-setup-board" />,
  EarningsBoard: () => <div data-testid="earnings-board" />,
  CatalystFeed: () => <div data-testid="catalyst-feed" />,
  SignalPerformanceBoard: () => <div data-testid="signal-performance-board" />,
}))

vi.mock('../components/WatchlistTable', () => ({
  WatchlistTable: () => <div data-testid="watchlist-table" />,
}))

vi.mock('../components/MarketMoodSectorBriefing', () => ({
  MarketMoodSectorBriefing: () => <div data-testid="market-mood-sector-briefing" />,
}))

vi.mock('../components/RiskIntelPanel', () => ({
  RiskIntelPanel: () => <div data-testid="risk-intel-panel" />,
}))

vi.mock('../utils/sectorMood', () => ({
  deriveSectorMoodInsights: vi.fn(() => ({
    hasSectorData: false,
    focus: [],
    watch: [],
    neutral: [],
    insights: [],
  })),
  buildMarketMoodSummary: vi.fn(() => 'market summary'),
}))

vi.mock('../utils/trader', () => ({
  buildCatalystFeedSections: vi.fn(() => ({ hard: [], medium: [], soft: [] })),
  buildEarningsBoardSections: vi.fn(() => []),
  buildSetupCards: vi.fn(() => []),
  buildSignalPerformanceHighlights: vi.fn(() => []),
  computeSetupScore: vi.fn(() => ({ score: 0 })),
  computeTargetUpsidePercent: vi.fn(() => null),
  getLatestCatalystItem: vi.fn(() => undefined),
  getNextEarningsEvent: vi.fn(() => undefined),
}))

describe('Dashboard today priority queue', () => {
  it('renders the priority queue before the existing decision strip', () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    const queueHeading = screen.getByRole('heading', { name: '오늘 점검 큐' })
    const stripHeading = screen.getByRole('heading', { name: '오늘 먼저 볼 판단' })

    expect(queueHeading).toBeInTheDocument()
    expect(queueHeading.compareDocumentPosition(stripHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    expect(screen.getByText('Risk and opportunity review')).toBeInTheDocument()
    expect(screen.getByText('Evidence refresh needed')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'AMD 상세' })).toHaveAttribute('href', '/ticker/AMD')
  })
})

function buildTicker({
  ticker,
  name,
  action,
  conviction,
  sector = 'Technology',
  newsTone = 'neutral',
  relativeVolume = 'N/A',
  rsVsSpy = 'N/A',
  rsVsSector = 'N/A',
}: {
  ticker: string
  name: string
  action: 'buy' | 'watch' | 'avoid'
  conviction: number
  sector?: string
  newsTone?: 'bullish' | 'neutral' | 'bearish'
  relativeVolume?: string
  rsVsSpy?: string
  rsVsSector?: string
}): TickerAnalysisData {
  return {
    ticker,
    name,
    date: '2026-05-21',
    summary: `${ticker} summary`,
    key_news: [],
    news_references: [],
    financial_highlights: [],
    risks_or_watchpoints: [],
    signal_or_takeaway: `${ticker} signal`,
    data_snapshot: { Sector: sector, 'Daily Change': 'N/A' },
    fundamentals: {},
    earnings_setup: {
      forward_eps: 'N/A',
      ttm_eps: 'N/A',
      forward_vs_ttm: 'N/A',
      earnings_growth: 'N/A',
      latest_estimated_eps: 'N/A',
      latest_surprise_pct: 'N/A',
      latest_beat_miss: 'N/A',
      next_earnings_event: 'N/A',
    },
    price_action: {
      atr_14d: 'N/A',
      atr_percent: 'N/A',
      relative_volume: relativeVolume,
      gap_percent: 'N/A',
      price_vs_sma50: 'N/A',
      price_vs_sma200: 'N/A',
      week52_position: 'N/A',
      rs_vs_spy: rsVsSpy,
      rs_vs_sector_etf: rsVsSector,
    },
    quarterly_financials: [],
    upcoming_events: [],
    news_tone: { label: newsTone, score: newsTone === 'bullish' ? 0.8 : 0 },
    trade_frame: {
      bull_scenario: 'Bull case',
      base_scenario: 'Base case',
      bear_scenario: 'Bear case',
      invalidation_price: 'N/A',
      watch_period: 'N/A',
    },
    period_changes: {},
    sec_filing_tags: [],
    sec_filings: [],
    decision: {
      action,
      conviction,
      reason: `${ticker} decision reason`,
      valid_until: '2026-05-30',
      factors: {},
    },
  } as TickerAnalysisData
}
