import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { OptionsAggregateEvent } from '../types/optionsLive'
import { OptionsLivePanel } from './OptionsLivePanel'

const hookState = vi.hoisted(() => ({
  contracts: [{ contract: 'O:AAPL260116C00200000', label: 'CALL 200 - 2026-01-16' }],
  selectedContract: 'O:AAPL260116C00200000',
  setSelectedContract: vi.fn(),
  manualContract: '',
  setManualContract: vi.fn(),
  selectManualContract: vi.fn(),
  rows: [] as OptionsAggregateEvent[],
  latest: null as OptionsAggregateEvent | null,
  status: 'missing_credentials',
  message: 'POLYGON_API_KEY or MASSIVE_API_KEY is not configured',
  recency: 'delayed_15m',
}))

vi.mock('../hooks/useOptionsLive', () => ({
  useOptionsLive: () => hookState,
}))

vi.mock('./OptionAggregateChart', () => ({
  OptionAggregateChart: () => <div data-testid="option-chart" />,
}))

describe('OptionsLivePanel', () => {
  beforeEach(() => {
    hookState.selectedContract = 'O:AAPL260116C00200000'
    hookState.rows = []
    hookState.latest = null
    hookState.status = 'missing_credentials'
    hookState.message = 'POLYGON_API_KEY or MASSIVE_API_KEY is not configured'
    hookState.setManualContract.mockClear()
    hookState.selectManualContract.mockClear()
  })

  it('shows delayed status and missing key state', () => {
    render(<OptionsLivePanel ticker="AAPL" />)
    expect(screen.getByText('DELAYED 15m')).toBeInTheDocument()
    expect(screen.getByText('NO KEY')).toBeInTheDocument()
    expect(screen.getByText('API key required')).toBeInTheDocument()
    expect(screen.queryByText('Last')).not.toBeInTheDocument()
  })

  it('allows manual contract submission', () => {
    render(<OptionsLivePanel ticker="AAPL" />)
    fireEvent.change(screen.getByLabelText('옵션 계약 직접 입력'), {
      target: { value: 'O:AAPL260116C00200000' },
    })
    fireEvent.click(screen.getByRole('button', { name: '적용' }))
    expect(hookState.setManualContract).toHaveBeenCalledWith('O:AAPL260116C00200000')
    expect(hookState.selectManualContract).toHaveBeenCalled()
  })

  it('shows diagnostics after an aggregate arrives', () => {
    hookState.status = 'connected'
    hookState.message = ''
    hookState.latest = {
      type: 'aggregate',
      source: 'polygon_options',
      recency: 'delayed_15m',
      channel: 'A',
      contract: 'O:AAPL260116C00200000',
      timestamp: 1780617600999,
      open: 3.1,
      high: 3.2,
      low: 3,
      close: 3.15,
      volume: 42,
      accumulated_volume: 120,
      vwap: 3.12,
    }

    render(<OptionsLivePanel ticker="AAPL" />)

    expect(screen.getByText('Last')).toBeInTheDocument()
    expect(screen.getByText('3.15')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.queryByText('API key required')).not.toBeInTheDocument()
  })
})
