import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { DashboardData } from '../types'
import { Portfolio } from './Portfolio'

const dashboardData: DashboardData = {
  days: [
    {
      date: '2026-05-13',
      market_overview: [],
      tickers: [],
      portfolio_summary: {
        total_market_value: 100_000,
        total_cost_basis: 90_000,
        total_unrealized_pnl: 10_000,
        total_unrealized_return_pct: 11.11,
        positions: [
          {
            ticker: 'AMD',
            shares: 100,
            avg_cost: 100,
            currency: 'USD',
            market_price: 130,
            market_value: 30_000,
            cost_basis: 10_000,
            unrealized_pnl: 20_000,
            unrealized_return_pct: 200,
          },
          {
            ticker: 'AAPL',
            shares: 100,
            avg_cost: 100,
            currency: 'USD',
            market_price: 180,
            market_value: 45_000,
            cost_basis: 10_000,
            unrealized_pnl: 35_000,
            unrealized_return_pct: 350,
          },
          {
            ticker: 'CAT',
            shares: 100,
            avg_cost: 100,
            currency: 'USD',
            market_price: 250,
            market_value: 25_000,
            cost_basis: 10_000,
            unrealized_pnl: 15_000,
            unrealized_return_pct: 150,
          },
        ],
      },
      portfolio_risk: {
        hhi: 3400,
        portfolio_beta: 1.24,
        var_95: 2.8,
        positions_by_weight: [
          { ticker: 'AAPL', weight_pct: 45, sector: 'Technology', market_value: 45_000, atr_risk_usd: 1800 },
          { ticker: 'AMD', weight_pct: 30, sector: 'Technology', market_value: 30_000, atr_risk_usd: 1200 },
          { ticker: 'CAT', weight_pct: 25, sector: 'Industrials', market_value: 25_000, atr_risk_usd: 900 },
        ],
        sector_exposure: {
          Technology: 75,
          Industrials: 25,
        },
        correlation_pairs: [
          {
            ticker_1: 'AAPL',
            ticker_2: 'AMD',
            correlation: '0.81',
            warning: '두 기술주가 같은 방향으로 움직일 가능성이 큽니다.',
          },
        ],
      },
      pm_view: {
        as_of: '2026-05-13',
        event_exposure_items: [
          {
            ticker: 'AMD',
            event_risk_score: 92,
            event_label: '실적 발표',
            event_date: '2026-05-15',
            days_until: 2,
            summary: '실적 발표 전 변동성이 커질 수 있습니다.',
            reasons: ['실적 변동성'],
            review_points: ['포지션 크기 확인'],
          },
        ],
        swap_candidates: [
          {
            held_ticker: 'AAPL',
            candidate_ticker: 'CAT',
            swap_candidate_score: 76,
            summary: '집중도 완화를 위해 대체 후보를 검토합니다.',
            reasons: ['집중도 완화'],
            overlap_context: '섹터 분산',
            review_points: ['AAPL 비중과 CAT 신규 비중 비교'],
          },
        ],
        today_priority_queue: [],
        empty_states: {},
      },
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

vi.mock('../hooks/useLocalPortfolioEditor', () => ({
  useLocalPortfolioEditor: () => ({
    status: {
      available: true,
      stage: 'idle',
      stageLabel: '대기',
      message: '테스트 포트폴리오',
      updatedAt: null,
      holdings: [],
    },
    loading: false,
    saving: false,
    refresh: vi.fn(),
    saveHoldings: vi.fn(),
  }),
}))

vi.mock('../components/EquityCurveChart', () => ({
  EquityCurveChart: () => <div data-testid="equity-curve-chart" />,
}))

vi.mock('../components/PortfolioRiskPanel', () => ({
  PortfolioRiskPanel: () => <div data-testid="portfolio-risk-panel" />,
}))

describe('Portfolio command center integration', () => {
  it('renders the command center ahead of the holdings table with PM and risk data', () => {
    render(
      <MemoryRouter>
        <Portfolio />
      </MemoryRouter>,
    )

    const commandHeading = screen.getByRole('heading', { name: 'Portfolio Command Center' })
    const summaryLabel = screen.getByText('평가 금액')

    expect(screen.getByText('실적 발표 전 변동성이 커질 수 있습니다.')).toBeInTheDocument()
    expect(screen.getByText('HHI 집중도')).toBeInTheDocument()
    expect(Boolean(commandHeading.compareDocumentPosition(summaryLabel) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true)
  })
})
