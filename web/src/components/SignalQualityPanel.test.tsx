import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SignalQualityPanel } from './SignalQualityPanel'

const signalQualityPayload = {
  rolling_ic: {
    status: 'ok',
    sample_size: 2,
    window_days: 90,
    step_days: 15,
    factors: [
      {
        factor: 'momentum',
        series: [
          { window_end: '2026-01-01', ic: 0.12, n: 10 },
          { window_end: '2026-01-15', ic: -0.04, n: 10 },
        ],
        latest_ic: -0.04,
        lifetime_avg_ic: 0.03,
        fatigue: false,
      },
    ],
  },
  ic_decay: { status: 'empty', sample_sizes: {}, factors: [] },
  kelly: { status: 'empty', horizon: 5, haircut: 0.5, by_direction: {} },
  turnover: { status: 'empty', sample_size: 0, points: [] },
}

describe('SignalQualityPanel accessibility', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('hides rolling IC sparklines from assistive tech because table text carries the values', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => signalQualityPayload,
      }),
    )

    const { container } = render(<SignalQualityPanel />)

    await screen.findByText('momentum')

    const sparkline = container.querySelector('td svg')
    expect(sparkline).toHaveAttribute('aria-hidden', 'true')
    expect(sparkline).toHaveAttribute('focusable', 'false')
  })
})
