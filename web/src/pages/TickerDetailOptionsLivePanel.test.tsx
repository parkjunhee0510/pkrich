import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { DashboardData, TickerAnalysisData } from '../types'
import { TickerDetail } from './TickerDetail'

const analysis: TickerAnalysisData = {
  ticker: 'AAPL',
  name: 'Apple Inc.',
  date: '2026-06-04',
  summary: 'summary',
  key_news: [],
  news_references: [],
  financial_highlights: [],
  risks_or_watchpoints: [],
  signal_or_takeaway: 'signal',
  data_snapshot: { Price: '200 USD', 'Daily Change': '+1.0%' },
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
  news_tone: { label: 'neutral', score: 0 },
  trade_frame: {
    bull_scenario: 'Bull',
    base_scenario: 'Base',
    bear_scenario: 'Bear',
    invalidation_price: 'N/A',
    watch_period: 'N/A',
  },
  period_changes: {},
  sec_filing_tags: [],
  sec_filings: [],
}

const dashboardData: DashboardData = {
  days: [{ date: '2026-06-04', market_overview: [], tickers: [analysis] }],
}

vi.mock('../hooks/useDashboardData', () => ({
  useDashboardData: () => ({ data: dashboardData, loading: false, error: null }),
}))

vi.mock('../hooks/useTickerAnalysis', () => ({
  useTickerAnalysis: () => ({ analysis }),
}))

vi.mock('../hooks/usePriceHistory', () => ({
  usePriceHistory: () => ({ rows: [], loading: false }),
}))

vi.mock('../hooks/useTickerTimeline', () => ({
  useTickerTimeline: () => ({ entries: [], loading: false }),
}))

vi.mock('../hooks/usePolicyData', () => ({
  usePolicyData: () => ({ data: null }),
}))

vi.mock('../hooks/useSearchEvidenceData', () => ({
  useSearchEvidenceData: () => ({ searchEvidence: null, loading: false, error: null }),
}))

vi.mock('../hooks/useQualityReliabilityLoopData', () => ({
  useQualityReliabilityLoopData: () => ({ qualityLoop: null, loading: false, error: null }),
}))

vi.mock('../hooks/useRiskIntelData', () => ({
  useRiskIntelData: () => ({ summary: null, graph: null, loading: false, error: null, graphError: null }),
}))

vi.mock('../components/OptionsLivePanel', () => ({
  OptionsLivePanel: ({ ticker, underlyingPrice }: { ticker: string; underlyingPrice?: number | null }) => (
    <div data-testid="options-live-panel">options {ticker} {underlyingPrice}</div>
  ),
}))

vi.mock('../utils/trader', () => ({
  buildPositionSizingSummary: () => ({ stopPrice: 'N/A', positionShares: 'N/A', riskReward: 'N/A' }),
  buildPriceActionTags: () => [],
  extractActionPlan: () => null,
  getLatestCatalystItem: () => null,
}))

describe('TickerDetail options live panel', () => {
  it('renders the options panel in the chart tab', async () => {
    render(
      <MemoryRouter initialEntries={['/ticker/AAPL']}>
        <Routes>
          <Route path="/ticker/:ticker" element={<TickerDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('tab', { name: '차트' }))

    expect(screen.getByTestId('options-live-panel')).toHaveTextContent('options AAPL 200')
  })
})
