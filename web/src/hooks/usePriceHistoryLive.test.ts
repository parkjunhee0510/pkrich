import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { usePriceHistoryLive } from './usePriceHistoryLive'
import type { PriceHistoryRow } from '../types'

function createDeferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

const rows: PriceHistoryRow[] = [
  {
    date: '2026-05-27',
    ticker: 'AAPL',
    price: '100',
    daily_change: '+1%',
    market_cap: 'N/A',
    trailing_pe: 'N/A',
    eps: 'N/A',
    '52w_high': 'N/A',
    '52w_low': 'N/A',
    open: 'N/A',
    high: 'N/A',
    low: 'N/A',
    close: 'N/A',
    volume: 'N/A',
  },
]

function jsonResponse<T>(payload: T) {
  return {
    ok: true,
    json: () => Promise.resolve(payload),
  } as Response
}

describe('usePriceHistoryLive', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps cached price rows visible on remount instead of showing the table skeleton again', async () => {
    const refresh = createDeferred<Response>()
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(rows))
      .mockReturnValueOnce(refresh.promise)

    const first = renderHook(() => usePriceHistoryLive())

    await waitFor(() => expect(first.result.current.loading).toBe(false))
    expect(first.result.current.allRows).toEqual(rows)

    first.unmount()

    const second = renderHook(() => usePriceHistoryLive())

    expect(second.result.current.allRows).toEqual(rows)
    expect(second.result.current.loading).toBe(false)

    await act(async () => {
      refresh.resolve(jsonResponse(rows))
      await refresh.promise
    })
  })
})
