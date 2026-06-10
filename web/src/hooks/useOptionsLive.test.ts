import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { buildOptionsWebSocketUrl, useOptionsLive } from './useOptionsLive'

class MockWebSocket {
  static instances: MockWebSocket[] = []

  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  url: string

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  close() {
    this.onclose?.()
  }

  emit(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent)
  }
}

describe('useOptionsLive', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.restoreAllMocks()
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  it('builds a ws URL from VITE_API_BASE', () => {
    const result = buildOptionsWebSocketUrl('http://localhost:8000', 'O:AAPL260116C00200000')
    expect(result).toBe('ws://localhost:8000/api/options/live?contract=O%3AAAPL260116C00200000&timespan=second')
  })

  it('loads contracts and opens a websocket for the first contract', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'ok',
        ticker: 'AAPL',
        recency: 'delayed_15m',
        contracts: [{ contract: 'O:AAPL260116C00200000', label: 'CALL 200 - 2026-01-16' }],
        message: '',
      }),
    })
    vi.stubGlobal(
      'fetch',
      fetchMock,
    )

    const { result } = renderHook(() =>
      useOptionsLive('AAPL', { enabled: true, apiBase: 'http://localhost:8000', underlyingPrice: 200 }),
    )

    await waitFor(() => expect(result.current.selectedContract).toBe('O:AAPL260116C00200000'))
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/options/contracts?ticker=AAPL&underlying_price=200',
      { cache: 'no-store' },
    )
    expect(MockWebSocket.instances).toHaveLength(1)

    act(() => {
      MockWebSocket.instances[0].emit({
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
        volume: 1,
        accumulated_volume: 2,
        vwap: 3.1,
      })
    })

    expect(result.current.rows).toHaveLength(1)
    expect(result.current.latest?.close).toBe(3.15)
  })
})
