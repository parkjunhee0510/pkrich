import { afterEach, describe, expect, it, vi } from 'vitest'

import { StaticJsonRepository } from './StaticJsonRepository'

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status })
}

describe('StaticJsonRepository', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('ignores unsupported index schema versions and falls back to supported history', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string | URL | Request) => {
        const href = String(url)
        if (href.includes('index.json')) {
          return jsonResponse({
            schema_version: 999,
            date: '2026-05-04',
            market_overview: [],
            tickers: [{ ticker: 'STALE' }],
          })
        }
        if (href.includes('dashboard_history.json')) {
          return jsonResponse({
            schema_version: 1,
            days: [
              {
                date: '2026-05-01',
                market_overview: [],
                market_regime: { confidence: 1 },
                tickers: [{ ticker: 'AAPL' }],
              },
            ],
          })
        }
        return jsonResponse({}, 404)
      }),
    )

    const dashboard = await new StaticJsonRepository().loadDashboard(1)

    expect(dashboard.schema_version).toBe(1)
    expect(dashboard.days).toHaveLength(1)
    expect(dashboard.days[0].date).toBe('2026-05-01')
    expect(dashboard.days[0].tickers[0].ticker).toBe('AAPL')
  })
})
