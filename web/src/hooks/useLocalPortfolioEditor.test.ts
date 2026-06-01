import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useLocalPortfolioEditor } from './useLocalPortfolioEditor'
import type { LocalPortfolioStatus, PortfolioHoldingInput } from '../types'

const statusPayload: LocalPortfolioStatus = {
  available: true,
  stage: 'idle',
  stageLabel: 'Idle',
  message: 'ready',
  updatedAt: null,
  holdings: [],
}

const holdings: PortfolioHoldingInput[] = [{ ticker: 'AAPL', shares: 12, avg_cost: 150, currency: 'USD' }]

describe('useLocalPortfolioEditor', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('serves the latest local portfolio status on remount while refreshing in the background', async () => {
    let resolveRefresh!: (response: Response) => void
    const refreshPromise = new Promise<Response>((resolve) => {
      resolveRefresh = resolve
    })
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json(statusPayload))
      .mockReturnValueOnce(refreshPromise)
    vi.stubGlobal('fetch', fetchMock)

    const first = renderHook(() => useLocalPortfolioEditor())

    await waitFor(() => expect(first.result.current.loading).toBe(false))
    expect(first.result.current.status).toEqual(statusPayload)

    first.unmount()

    const second = renderHook(() => useLocalPortfolioEditor())

    expect(second.result.current.status).toEqual(statusPayload)
    expect(second.result.current.loading).toBe(false)

    await act(async () => {
      resolveRefresh(Response.json(statusPayload))
      await refreshPromise
    })
  })

  it('includes delete approval only when saving an intentional truncation', async () => {
    const fetchMock = vi.fn(async (url: string | URL | Request) => {
      const requestUrl = String(url)
      if (requestUrl === '/api/local-portfolio/status') {
        return Response.json(statusPayload)
      }
      if (requestUrl === '/api/local-portfolio/save') {
        return Response.json({ ok: true, message: 'saved', status: statusPayload })
      }
      throw new Error(`Unexpected URL: ${requestUrl}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useLocalPortfolioEditor())

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/local-portfolio/status', { cache: 'no-store' }))
    await act(async () => {
      await result.current.saveHoldings(holdings, { allowTruncate: true })
    })

    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/local-portfolio/save',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ holdings, allowTruncate: true }),
      }),
    )
  })
})
