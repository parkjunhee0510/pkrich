import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { DashboardRepository } from '../data/DashboardRepository'
import type { DashboardData } from '../types'
import { useDashboardData } from './useDashboardData'

function createDeferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

const dashboardPayload = {
  schema_version: 1,
  days: [{ date: '2026-05-27', market_overview: [], tickers: [] }],
  signal_stats: { recent_signals: [], summary_by_direction: {} },
} as DashboardData

function createRepository(loadDashboard: () => Promise<DashboardData>): DashboardRepository {
  return {
    loadDashboard: vi.fn(loadDashboard),
    loadTickerLatest: vi.fn(),
    loadTickerHistory: vi.fn(),
  }
}

describe('useDashboardData', () => {
  it('serves cached dashboard data without returning to the full loading state', async () => {
    const firstLoad = createDeferred<DashboardData>()
    const secondLoad = createDeferred<DashboardData>()
    const repository = createRepository(vi.fn()
      .mockReturnValueOnce(firstLoad.promise)
      .mockReturnValueOnce(secondLoad.promise))

    const first = renderHook(() => useDashboardData({ repository }))

    expect(first.result.current.loading).toBe(true)

    await act(async () => {
      firstLoad.resolve(dashboardPayload)
      await firstLoad.promise
    })
    await waitFor(() => expect(first.result.current.loading).toBe(false))

    first.unmount()

    const second = renderHook(() => useDashboardData({ repository }))

    expect(second.result.current.data).toBe(dashboardPayload)
    expect(second.result.current.loading).toBe(false)

    await act(async () => {
      secondLoad.resolve(dashboardPayload)
      await secondLoad.promise
    })
  })
})
