import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { DashboardData, TickerAnalysisData } from '../types'
import { Dashboard } from './Dashboard'

const dashboardData: DashboardData = {
  days: [
    {
      date: '2026-05-28',
      market_overview: [
        {
          label: 'S&P 500',
          symbol: 'SPY',
          price: '5,920',
          change: '+0.8%',
        },
      ],
      market_regime: {
        regime: 'risk_on',
        confidence: 74,
        drivers: {
          vix: 'VIX stable',
          breadth: 'positive breadth',
        },
        implication: 'Growth and cyclical sectors remain first checks.',
        assessed_at: '2026-05-28T00:00:00Z',
      },
      macro_context: {
        oil_wti: { price: '$78.12', change: '+1.4%' },
        gold: { price: '$2,410', change: '-0.2%' },
        dxy: { level: '104.2', change: '+0.1%' },
        us10y: { level: '4.41%', change: '-3bp' },
      },
      tickers: [
        buildTicker({
          ticker: 'AMD',
          name: 'Advanced Micro Devices',
          sector: 'Semiconductors',
          action: 'buy',
          conviction: 82,
          keyNews: ['AI server demand is lifting AMD sentiment.'],
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

vi.mock('../hooks/useRiskIntelData', () => ({
  useRiskIntelData: () => ({
    summary: null,
    graph: null,
    loading: false,
    error: null,
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

describe('Dashboard news desk integration', () => {
  it('renders the news desk before the priority queue while preserving the watchlist', () => {
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

    expect(screen.getByRole('region', { name: '오늘의 뉴스 데스크' })).toBeInTheDocument()
    expect(screen.getByText('오늘의 상황판')).toBeInTheDocument()
    expect(screen.getByText('위험자산 선호')).toBeInTheDocument()
    expect(screen.getByText('유가 WTI')).toBeInTheDocument()
    expect(screen.getByText('금')).toBeInTheDocument()
    expect(screen.getByTestId('watchlist-table')).toBeInTheDocument()

    const newsDesk = document.querySelector('.news-desk')
    const priorityQueue = document.querySelector('.today-priority-queue-section')

    expect(newsDesk).not.toBeNull()
    expect(priorityQueue).not.toBeNull()
    expect(newsDesk?.compareDocumentPosition(priorityQueue as Element)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })
})

function buildTicker({
  ticker,
  name,
  sector,
  action,
  conviction,
  keyNews,
}: {
  ticker: string
  name: string
  sector: string
  action: 'buy' | 'watch' | 'avoid'
  conviction: number
  keyNews: string[]
}): TickerAnalysisData {
  return {
    ticker,
    name,
    date: '2026-05-28',
    summary: `${ticker} summary`,
    key_news: keyNews,
    news_references: [],
    financial_highlights: [],
    risks_or_watchpoints: [],
    signal_or_takeaway: `${ticker} signal`,
    data_snapshot: {
      Sector: sector,
      'Daily Change': '+2.1%',
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
      relative_volume: '1.3',
      gap_percent: 'N/A',
      price_vs_sma50: 'N/A',
      price_vs_sma200: 'N/A',
      week52_position: 'N/A',
      rs_vs_spy: '+2.0%',
      rs_vs_sector_etf: '+0.7%',
    },
    quarterly_financials: [],
    upcoming_events: [],
    news_tone: { label: 'bullish', score: 0.7 },
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
      reason: `${ticker} buy decision`,
      valid_until: '2026-06-04',
      factors: {},
    },
  }
}
