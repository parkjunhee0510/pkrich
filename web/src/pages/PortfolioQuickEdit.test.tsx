import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { DashboardData, PortfolioHoldingInput } from '../types'
import { Portfolio } from './Portfolio'

const saveHoldings = vi.fn()
let mockHoldings: PortfolioHoldingInput[] = []

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
            ticker: 'AAPL',
            shares: 12,
            avg_cost: 150,
            currency: 'USD',
            market_price: 180,
            market_value: 2160,
            cost_basis: 1800,
            unrealized_pnl: 360,
            unrealized_return_pct: 20,
          },
          {
            ticker: 'CAT',
            shares: 3,
            avg_cost: 330,
            currency: 'USD',
            market_price: 350,
            market_value: 1050,
            cost_basis: 990,
            unrealized_pnl: 60,
            unrealized_return_pct: 6.06,
          },
        ],
      },
      portfolio_risk: null,
      pm_view: null,
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
      holdings: mockHoldings,
    },
    loading: false,
    saving: false,
    refresh: vi.fn(),
    saveHoldings,
  }),
}))

vi.mock('../components/EquityCurveChart', () => ({
  EquityCurveChart: () => <div data-testid="equity-curve-chart" />,
}))

vi.mock('../components/PortfolioCommandCenter', () => ({
  PortfolioCommandCenter: () => <div data-testid="portfolio-command-center" />,
}))

vi.mock('../components/PortfolioRiskPanel', () => ({
  PortfolioRiskPanel: () => <div data-testid="portfolio-risk-panel" />,
}))

function renderPortfolio() {
  return render(
    <MemoryRouter>
      <Portfolio />
    </MemoryRouter>,
  )
}

describe('Portfolio quick edit', () => {
  beforeEach(() => {
    mockHoldings = [
      { ticker: 'AAPL', shares: 12, avg_cost: 150, currency: 'USD' },
      { ticker: 'AMD', shares: 5, avg_cost: 100, currency: 'USD' },
    ]
    saveHoldings.mockClear()
    saveHoldings.mockResolvedValue({
      ok: true,
      message: 'saved',
      status: {
        available: true,
        stage: 'saved',
        stageLabel: '저장됨',
        message: 'saved',
        updatedAt: null,
        holdings: mockHoldings,
      },
    })
  })

  it('renders existing lot rows immediately in edit mode', () => {
    renderPortfolio()

    fireEvent.click(screen.getByRole('button', { name: '포트폴리오 편집' }))

    expect(screen.getByRole('button', { name: 'AAPL ticker selector' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'AMD ticker selector' })).toBeInTheDocument()
    expect(screen.queryByText('펼치기')).not.toBeInTheDocument()
  })

  it('shows a starter row for an empty local portfolio', () => {
    mockHoldings = []

    renderPortfolio()

    fireEvent.click(screen.getByRole('button', { name: '포트폴리오 편집' }))

    expect(screen.getByRole('button', { name: '새 lot 1 ticker selector' })).toBeInTheDocument()
    expect(screen.getByText('티커 선택')).toBeInTheDocument()
    expect(screen.getByText('0개 변경')).toBeInTheDocument()
  })

  it('selects ticker from the list before saving', async () => {
    renderPortfolio()

    fireEvent.click(screen.getByRole('button', { name: '포트폴리오 편집' }))
    fireEvent.click(screen.getByRole('button', { name: 'AAPL ticker selector' }))
    fireEvent.click(within(screen.getByRole('listbox', { name: '티커 선택 목록' })).getByRole('option', { name: 'AMD' }))
    fireEvent.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(saveHoldings).toHaveBeenCalledTimes(1))
    expect(saveHoldings).toHaveBeenCalledWith([
      { ticker: 'AMD', shares: 12, avg_cost: 150, currency: 'USD' },
      { ticker: 'AMD', shares: 5, avg_cost: 100, currency: 'USD' },
    ])
  })

  it('defaults average cost to current price when selecting ticker for a new lot', async () => {
    mockHoldings = []

    const { container } = renderPortfolio()

    const [, editButton] = Array.from(container.querySelectorAll('.preset-chip'))
    fireEvent.click(editButton)

    const tickerButton = container.querySelector('.portfolio-ticker-picker-button')
    expect(tickerButton).not.toBeNull()
    fireEvent.click(tickerButton as HTMLButtonElement)
    fireEvent.click(screen.getByRole('option', { name: 'AAPL' }))

    const [, avgCostInput] = screen.getAllByRole('spinbutton')
    expect(avgCostInput).toHaveValue(180)

    const saveButton = container.querySelector('.primary-action-button')
    expect(saveButton).not.toBeNull()
    fireEvent.click(saveButton as HTMLButtonElement)

    await waitFor(() => expect(saveHoldings).toHaveBeenCalledTimes(1))
    expect(saveHoldings).toHaveBeenCalledWith([
      { ticker: 'AAPL', shares: 1, avg_cost: 180, currency: 'USD' },
    ])
  })

  it('updates an auto-filled average cost when switching selected ticker', async () => {
    mockHoldings = []

    const { container } = renderPortfolio()

    const [, editButton] = Array.from(container.querySelectorAll('.preset-chip'))
    fireEvent.click(editButton)

    let tickerButton = container.querySelector('.portfolio-ticker-picker-button')
    expect(tickerButton).not.toBeNull()
    fireEvent.click(tickerButton as HTMLButtonElement)
    fireEvent.click(screen.getByRole('option', { name: 'CAT' }))

    let [, avgCostInput] = screen.getAllByRole('spinbutton')
    expect(avgCostInput).toHaveValue(350)

    tickerButton = container.querySelector('.portfolio-ticker-picker-button')
    expect(tickerButton).not.toBeNull()
    fireEvent.click(tickerButton as HTMLButtonElement)
    fireEvent.click(screen.getByRole('option', { name: 'AAPL' }))

    ;[, avgCostInput] = screen.getAllByRole('spinbutton')
    expect(avgCostInput).toHaveValue(180)

    const saveButton = container.querySelector('.primary-action-button')
    expect(saveButton).not.toBeNull()
    fireEvent.click(saveButton as HTMLButtonElement)

    await waitFor(() => expect(saveHoldings).toHaveBeenCalledTimes(1))
    expect(saveHoldings).toHaveBeenCalledWith([
      { ticker: 'AAPL', shares: 1, avg_cost: 180, currency: 'USD' },
    ])
  })

  it('saves edited holdings from the quick edit rows', async () => {
    renderPortfolio()

    fireEvent.click(screen.getByRole('button', { name: '포트폴리오 편집' }))
    fireEvent.change(screen.getByLabelText('AAPL 수량'), { target: { value: '20' } })
    fireEvent.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(saveHoldings).toHaveBeenCalledTimes(1))
    expect(saveHoldings).toHaveBeenCalledWith([
      { ticker: 'AAPL', shares: 20, avg_cost: 150, currency: 'USD' },
      { ticker: 'AMD', shares: 5, avg_cost: 100, currency: 'USD' },
    ])
  })

  it('marks a shorter save as an intentional deletion only after deleting a lot', async () => {
    const { container } = renderPortfolio()

    const [, editButton] = Array.from(container.querySelectorAll('.preset-chip'))
    fireEvent.click(editButton)

    const [, deleteSecondLot] = Array.from(container.querySelectorAll('.portfolio-delete-lot-button'))
    fireEvent.click(deleteSecondLot)

    const saveButton = container.querySelector('.primary-action-button')
    expect(saveButton).not.toBeNull()
    fireEvent.click(saveButton as HTMLButtonElement)

    await waitFor(() => expect(saveHoldings).toHaveBeenCalledTimes(1))
    expect(saveHoldings).toHaveBeenCalledWith(
      [{ ticker: 'AAPL', shares: 12, avg_cost: 150, currency: 'USD' }],
      { allowTruncate: true },
    )
  })
})
