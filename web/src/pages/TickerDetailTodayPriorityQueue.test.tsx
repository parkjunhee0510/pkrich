import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { DashboardData, TickerAnalysisData } from '../types'
import { TickerDetail } from './TickerDetail'

const traderDecisionBoardCalls = vi.hoisted(() => [] as Array<Record<string, unknown>>)

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
          action: 'avoid',
          conviction: 32,
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
          action: 'watch',
          conviction: 48,
          upcomingEvents: [
            {
              type: 'earnings',
              label: 'Earnings',
              date: '2026-05-24',
              days_until: '3',
              timing: 'post-market',
            },
          ],
        }),
        buildTicker({
          ticker: 'NODEC',
          name: 'No Decision Corp',
          action: null,
          conviction: null,
        }),
      ],
    },
  ],
}

vi.mock('../hooks/useDashboardData', () => ({
  useDashboardData: () => ({
    data: dashboardData,
    loading: false,
    error: null,
  }),
}))

vi.mock('../hooks/useTickerAnalysis', () => ({
  useTickerAnalysis: () => ({ analysis: null }),
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
  useRiskIntelData: () => ({
    summary: null,
    graph: null,
    loading: false,
    error: null,
    graphError: null,
  }),
}))

vi.mock('../components/DecisionCard', () => ({
  DecisionCard: () => <div data-testid="decision-card" />,
}))

vi.mock('../components/SearchEvidenceBadge', () => ({
  SearchEvidencePanel: () => <div data-testid="search-evidence-panel" />,
}))

vi.mock('../components/TraderDecisionBoard', () => ({
  TraderDecisionBoard: (props: Record<string, unknown>) => {
    traderDecisionBoardCalls.push(props)
    return <div data-testid="trader-decision-board" />
  },
}))

vi.mock('../utils/trader', () => ({
  buildPositionSizingSummary: () => ({ stopPrice: 'N/A', positionShares: 'N/A', riskReward: 'N/A' }),
  buildPriceActionTags: () => [],
  extractActionPlan: () => ({
    direction: 'WATCH',
    thesis: 'Mock action plan',
    entry: '100 USD',
    invalidation: '95 USD',
    nextCatalyst: 'Mock event',
  }),
  getLatestCatalystItem: () => null,
}))

describe('TickerDetail today priority queue brief', () => {
  it('uses previous-day context so action-change queue items match the dashboard', () => {
    render(
      <MemoryRouter initialEntries={['/ticker/AMD']}>
        <Routes>
          <Route path="/ticker/:ticker" element={<TickerDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '오늘 올라온 이유' })).toBeInTheDocument()
    expect(screen.getByText('AMD · Score 12 · WATCH')).toBeInTheDocument()
    expect(screen.getByText('공식 판단이 AVOID에서 WATCH로 변경됨')).toBeInTheDocument()
    expect(screen.queryByText('오늘 우선 점검 큐에는 포함되지 않았습니다.')).not.toBeInTheDocument()
  })

  it('passes current, previous, event, and price context into the trader decision board', () => {
    traderDecisionBoardCalls.length = 0

    render(
      <MemoryRouter initialEntries={['/ticker/AMD']}>
        <Routes>
          <Route path="/ticker/:ticker" element={<TickerDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByTestId('trader-decision-board')).toBeInTheDocument()
    expect(traderDecisionBoardCalls).toHaveLength(1)

    const props = traderDecisionBoardCalls[0] as {
      decision?: { action: string; conviction: number }
      previousDecision?: { action: string; conviction: number }
      upcomingEvents?: Array<{ label: string; days_until: string }>
      currentPrice?: string
    }

    expect(props.decision).toMatchObject({ action: 'watch', conviction: 48 })
    expect(props.previousDecision).toMatchObject({ action: 'avoid', conviction: 32 })
    expect(props.upcomingEvents).toEqual([
      expect.objectContaining({ label: 'Earnings', days_until: '3' }),
    ])
    expect(props.currentPrice).toBe('100 USD')
  })

  it('groups the official decision and today brief in a shallow research desk', () => {
    traderDecisionBoardCalls.length = 0

    render(
      <MemoryRouter initialEntries={['/ticker/AMD']}>
        <Routes>
          <Route path="/ticker/:ticker" element={<TickerDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    const desk = screen.getByLabelText('종목 리서치 데스크')
    const grid = desk.querySelector('.ticker-research-desk-grid')
    const brief = screen.getByRole('heading', { name: '오늘 올라온 이유' }).closest('section')

    const evidencePanel = screen.getByTestId('search-evidence-panel')

    expect(grid).not.toBeNull()
    expect(grid).toContainElement(screen.getByTestId('decision-card'))
    expect(grid).toContainElement(brief)
    expect(grid?.nextElementSibling).toBe(evidencePanel)
    expect(desk).toContainElement(evidencePanel)
    expect(grid).not.toContainElement(evidencePanel)
  })

  it('lets the today brief span the research grid when the official decision is missing', () => {
    traderDecisionBoardCalls.length = 0

    render(
      <MemoryRouter initialEntries={['/ticker/NODEC']}>
        <Routes>
          <Route path="/ticker/:ticker" element={<TickerDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    const desk = screen.getByLabelText('종목 리서치 데스크')
    const grid = desk.querySelector('.ticker-research-desk-grid')
    const brief = screen.getByRole('heading', { name: '오늘 올라온 이유' }).closest('section')

    expect(grid).not.toBeNull()
    expect(grid).toContainElement(brief)
    expect(grid?.children).toHaveLength(1)
    expect(brief).toHaveClass('ticker-research-brief')
  })
})

function buildTicker({
  ticker,
  name,
  action,
  conviction,
  upcomingEvents = [],
}: {
  ticker: string
  name: string
  action: 'buy' | 'watch' | 'avoid' | null
  conviction: number | null
  upcomingEvents?: TickerAnalysisData['upcoming_events']
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
    data_snapshot: {
      Sector: 'Semiconductors',
      Price: '100 USD',
      'Daily Change': '+0.5%',
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
    upcoming_events: upcomingEvents,
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
    decision:
      action && conviction !== null
        ? {
            action,
            conviction,
            reason: `${ticker} decision reason`,
            valid_until: '2026-05-30',
            factors: {},
          }
        : undefined,
  }
}
