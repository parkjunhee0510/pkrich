import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { DashboardData, TickerAnalysisData } from '../types'
import { Dashboard } from './Dashboard'

const dashboardData: DashboardData = {
  days: [
    {
      date: '2026-04-29',
      market_overview: [],
      macro_context: null,
      market_regime: null,
      tickers: [
        buildTicker({
          ticker: 'ALAB',
          name: 'Astera Labs',
          action: 'watch',
          conviction: 52,
          sector: 'Technology',
        }),
        buildTicker({
          ticker: 'CAT',
          name: 'Caterpillar',
          action: 'buy',
          conviction: 72,
          sector: 'Industrials',
        }),
      ],
    },
    {
      date: '2026-04-30',
      market_overview: [],
      macro_context: null,
      market_regime: null,
      tickers: [],
    },
    {
      date: '2026-05-01',
      market_overview: [],
      macro_context: null,
      market_regime: null,
      tickers: [
        buildTicker({
          ticker: 'ALAB',
          name: 'Astera Labs',
          action: 'buy',
          conviction: 72,
          sector: 'Technology',
          qualityScore: 0.9,
        }),
        buildTicker({
          ticker: 'CAT',
          name: 'Caterpillar',
          action: 'watch',
          conviction: 63,
          sector: 'Industrials',
          qualityScore: 0.52,
          wouldCapAction: true,
          relativeVolume: '1.4',
        }),
      ],
    },
  ],
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
  useSearchEvidenceData: () => ({ searchEvidence: null, loading: false, error: null }),
}))

vi.mock('../hooks/useQualityReliabilityLoopData', () => ({
  useQualityReliabilityLoopData: () => ({ qualityLoop: null, loading: false, error: null }),
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

describe('Dashboard action change consolidation', () => {
  it('removes the today decision strip and adds its compact metrics to action change cards', () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    const feedHeading = screen.getByRole('heading', { name: '오늘 판단 변화' })
    const feed = feedHeading.closest('section')
    expect(feed).not.toBeNull()
    const feedQueries = within(feed!)

    expect(screen.queryByRole('heading', { name: '오늘 먼저 볼 판단' })).not.toBeInTheDocument()
    expect(feedQueries.getByText('quality 0.90')).toBeInTheDocument()
    expect(feedQueries.getByText('+20p')).toBeInTheDocument()
    expect(feedQueries.getByText('Technology')).toBeInTheDocument()
  })

  it('keeps action change entries visible when watchlist filters hide all rows', () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByPlaceholderText('티커 또는 종목명 검색'), {
      target: { value: 'NO_MATCH' },
    })

    const feed = document.querySelector<HTMLElement>('.action-change-feed-section')
    expect(feed).not.toBeNull()
    const feedQueries = within(feed!)

    expect(screen.queryByRole('heading', { name: '오늘 먼저 볼 판단' })).not.toBeInTheDocument()
    expect(feedQueries.getByText('BUY -> WATCH')).toBeInTheDocument()
    expect(feedQueries.getByText('WATCH -> BUY')).toBeInTheDocument()
    expect(screen.getByText('현재 보기: 0 / 2')).toBeInTheDocument()
  })
})

function buildTicker({
  ticker,
  name,
  action,
  conviction,
  sector = 'Technology',
  qualityScore,
  wouldCapAction = false,
  relativeVolume = 'N/A',
}: {
  ticker: string
  name: string
  action: 'buy' | 'watch' | 'avoid'
  conviction: number
  sector?: string
  qualityScore?: number
  wouldCapAction?: boolean
  relativeVolume?: string
}): TickerAnalysisData {
  return {
    ticker,
    name,
    date: '2026-05-01',
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
      rs_vs_spy: 'N/A',
      rs_vs_sector_etf: 'N/A',
    },
    quarterly_financials: [],
    upcoming_events: [],
    news_tone: { label: 'neutral', score: 0 },
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
      valid_until: '2026-05-10',
      factors: {},
      confidence_meta:
        qualityScore === undefined
          ? undefined
          : {
              data_quality_score: qualityScore,
              data_quality_gate: {
                would_cap_action: wouldCapAction,
                max_action_if_enforced: 'watch',
              },
            },
    },
  } as TickerAnalysisData
}
