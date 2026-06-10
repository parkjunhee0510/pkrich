import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { OptionAggregateChart } from './OptionAggregateChart'

vi.mock('lightweight-charts', () => ({
  ColorType: { Solid: 'Solid' },
  LineSeries: 'LineSeries',
  createChart: vi.fn(() => ({
    addSeries: vi.fn(() => ({ setData: vi.fn() })),
    applyOptions: vi.fn(),
    remove: vi.fn(),
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
  })),
}))

describe('OptionAggregateChart', () => {
  it('shows an empty state without rows', () => {
    render(<OptionAggregateChart rows={[]} contract="O:AAPL260116C00200000" />)
    expect(screen.getByText('옵션 초봉 데이터가 없습니다.')).toBeInTheDocument()
  })

  it('renders chart container for option aggregate rows', () => {
    render(
      <OptionAggregateChart
        contract="O:AAPL260116C00200000"
        rows={[{
          type: 'aggregate',
          source: 'polygon_options',
          recency: 'delayed_15m',
          channel: 'A',
          contract: 'O:AAPL260116C00200000',
          timestamp: 1780617600999,
          open: 3,
          high: 3.2,
          low: 2.9,
          close: 3.15,
          volume: 10,
          accumulated_volume: 20,
          vwap: 3.1,
        }]}
      />,
    )
    expect(screen.getByRole('img', { name: /O:AAPL260116C00200000 옵션 초봉 차트/ })).toBeInTheDocument()
  })
})
