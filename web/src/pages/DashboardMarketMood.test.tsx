import { render, screen } from '@testing-library/react'
import { MemoryRouter, Link } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { DashboardData, TickerAnalysisData } from '../types'
import { Dashboard } from './Dashboard'

const dashboardData: DashboardData = {
  days: [
    {
      date: '2026-04-30',
      market_regime: {
        regime: 'risk_on',
        confidence: 72,
        drivers: { vix: 'VIX 안정' },
        implication: '성장 섹터 우선 확인',
        assessed_at: '2026-04-30T00:00:00Z',
      },
      macro_context: null,
      market_overview: [],
      tickers: [
        buildTicker({
          ticker: 'NVDA',
          name: 'NVIDIA',
          sector: 'Semiconductors',
          dailyChange: '+2.4%',
          action: 'buy',
          conviction: 88,
          factors: { macro_regime: 8, regime_adjustment: 15, macro_event: 6 },
        }),
        buildTicker({
          ticker: 'NEE',
          name: 'NextEra Energy',
          sector: 'Utilities',
          dailyChange: '-0.6%',
          action: 'avoid',
          conviction: 35,
          factors: { macro_regime: -6, regime_adjustment: -15, macro_event: -8 },
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

vi.mock('../hooks/useLocalResearchAutomation', () => ({
  useLocalResearchAutomation: () => ({
    status: {
      available: false,
      running: false,
      stage: 'idle',
      stageLabel: '대기',
      message: '로컬 자동화 비활성',
      lastTicker: null,
      startedAt: null,
      finishedAt: null,
      updatedAt: null,
      lastResult: 'idle',
    },
    available: false,
    pendingAction: null,
    addTickerToWatchlist: vi.fn(),
    runResearch: vi.fn(),
  }),
}))

vi.mock('../components/PmDailyQueue', () => ({
  PmDailyQueue: () => <div data-testid="pm-daily-queue" />,
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
  MarketMoodSectorBriefing: ({ sectorMood }: { sectorMood: { focus: Array<{ representativeTickers: Array<{ ticker: string }> }>; watch: unknown[] } }) => (
    <section>
      <h2>오늘의 시장 해석</h2>
      <h3>주목 섹터</h3>
      <h3>주의 섹터</h3>
      {sectorMood.focus.flatMap((insight) =>
        insight.representativeTickers.map((ticker) => (
          <Link key={ticker.ticker} to={`/ticker/${ticker.ticker}`}>
            {ticker.ticker}
          </Link>
        )),
      )}
    </section>
  ),
}))

vi.mock('../utils/sectorMood', () => ({
  deriveSectorMoodInsights: vi.fn(() => ({
    hasSectorData: true,
    focus: [
      {
        sector: 'Semiconductors',
        representativeTickers: [{ ticker: 'NVDA' }],
      },
    ],
    watch: [
      {
        sector: 'Utilities',
        representativeTickers: [{ ticker: 'NEE' }],
      },
    ],
    neutral: [],
    insights: [],
  })),
  buildMarketMoodSummary: vi.fn(() => 'risk_on · 주목 1개 / 주의 1개 · 매크로와 섹터 흐름'),
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

describe('Dashboard market mood briefing', () => {
  it('renders the market mood briefing and accordion summary', () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    expect(screen.getByText('오늘 시장 분위기')).toBeInTheDocument()
    expect(screen.getByText('risk_on · 주목 1개 / 주의 1개 · 매크로와 섹터 흐름')).toBeInTheDocument()
    expect(screen.getByText('오늘의 시장 해석')).toBeInTheDocument()
    expect(screen.getByText('주목 섹터')).toBeInTheDocument()
    expect(screen.getByText('주의 섹터')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'NVDA' })).toBeInTheDocument()
  })
})

function buildTicker({
  ticker,
  name,
  sector,
  dailyChange,
  action,
  conviction,
  factors,
}: {
  ticker: string
  name: string
  sector: string
  dailyChange: string
  action: 'buy' | 'watch' | 'avoid'
  conviction: number
  factors: Record<string, number>
}): TickerAnalysisData {
  return {
    ticker,
    name,
    date: '2026-04-30',
    summary: `${ticker} summary`,
    key_news: [],
    news_references: [],
    financial_highlights: [],
    risks_or_watchpoints: [],
    signal_or_takeaway: `${ticker} signal`,
    data_snapshot: {
      Sector: sector,
      'Daily Change': dailyChange,
    },
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
      relative_volume: 'N/A',
      gap_percent: 'N/A',
      price_vs_sma50: 'N/A',
      price_vs_sma200: 'N/A',
      week52_position: 'N/A',
      rs_vs_spy: 'N/A',
      rs_vs_sector_etf: 'N/A',
    },
    quarterly_financials: [],
    upcoming_events: [],
    news_tone: {
      label: action === 'avoid' ? 'bearish' : 'bullish',
      score: action === 'avoid' ? -0.5 : 0.7,
    },
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
      reason: `${ticker} decision`,
      valid_until: '2026-05-07',
      factors,
    },
  }
}
