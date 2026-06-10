import { useEffect, useMemo, useState } from 'react'
import type {
  OptionsAggregateEvent,
  OptionsContract,
  OptionsContractLookupPayload,
  OptionsLiveEvent,
} from '../types/optionsLive'

export type OptionsLiveStatus =
  | 'idle'
  | 'loading'
  | 'connecting'
  | 'connected'
  | 'missing_credentials'
  | 'provider_auth_failed'
  | 'provider_no_access'
  | 'invalid_contract'
  | 'provider_disconnected'
  | 'rate_limited'
  | 'error'

interface UseOptionsLiveOptions {
  enabled?: boolean
  apiBase?: string
  underlyingPrice?: number | null
}

const DEFAULT_API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''
const MAX_ROWS = 900

export function buildOptionsWebSocketUrl(apiBase: string, contract: string): string {
  const base = apiBase || window.location.origin
  const url = new URL('/api/options/live', base)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.searchParams.set('contract', contract)
  url.searchParams.set('timespan', 'second')
  return url.toString()
}

function contractLookupUrl(apiBase: string, ticker: string, underlyingPrice?: number | null): string {
  const base = apiBase || window.location.origin
  const url = new URL('/api/options/contracts', base)
  url.searchParams.set('ticker', ticker)
  if (typeof underlyingPrice === 'number' && Number.isFinite(underlyingPrice) && underlyingPrice > 0) {
    url.searchParams.set('underlying_price', String(underlyingPrice))
  }
  return url.toString()
}

function isAggregateEvent(value: OptionsLiveEvent): value is OptionsAggregateEvent {
  return value.type === 'aggregate'
}

export function useOptionsLive(ticker?: string, options: UseOptionsLiveOptions = {}) {
  const enabled = options.enabled ?? true
  const apiBase = options.apiBase ?? DEFAULT_API_BASE
  const underlyingPrice = options.underlyingPrice ?? null
  const [contracts, setContracts] = useState<OptionsContract[]>([])
  const [selectedContract, setSelectedContract] = useState('')
  const [manualContract, setManualContract] = useState('')
  const [rows, setRows] = useState<OptionsAggregateEvent[]>([])
  const [status, setStatus] = useState<OptionsLiveStatus>('idle')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!enabled || !ticker) return
    let cancelled = false
    setStatus('loading')
    fetch(contractLookupUrl(apiBase, ticker, underlyingPrice), { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json() as Promise<OptionsContractLookupPayload>
      })
      .then((payload) => {
        if (cancelled) return
        setContracts(payload.contracts ?? [])
        setMessage(payload.message ?? '')
        setStatus(payload.status === 'ok' || payload.status === 'empty' ? 'idle' : (payload.status as OptionsLiveStatus))
        setSelectedContract((current) => current || payload.contracts?.[0]?.contract || '')
      })
      .catch((error: Error) => {
        if (cancelled) return
        setStatus('error')
        setMessage(error.message)
      })
    return () => {
      cancelled = true
    }
  }, [apiBase, enabled, ticker, underlyingPrice])

  useEffect(() => {
    if (!enabled || !selectedContract) return
    const socket = new WebSocket(buildOptionsWebSocketUrl(apiBase, selectedContract))
    setStatus('connecting')
    setRows([])
    socket.onopen = () => setStatus('connecting')
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(String(event.data)) as OptionsLiveEvent
        if (isAggregateEvent(payload)) {
          setRows((current) => [...current, payload].slice(-MAX_ROWS))
          setStatus('connected')
          setMessage('')
        } else if (payload.type === 'status') {
          setStatus(payload.status as OptionsLiveStatus)
          setMessage(payload.message ?? '')
        }
      } catch {
        setStatus('error')
        setMessage('Invalid options stream message')
      }
    }
    socket.onclose = () => {
      setStatus((current) => current === 'connected' ? 'provider_disconnected' : current)
    }
    socket.onerror = () => {
      setStatus('provider_disconnected')
    }
    return () => socket.close()
  }, [apiBase, enabled, selectedContract])

  const latest = rows.at(-1) ?? null
  const selectManualContract = () => {
    const normalized = manualContract.trim().toUpperCase()
    if (normalized) setSelectedContract(normalized)
  }

  return useMemo(
    () => ({
      contracts,
      selectedContract,
      setSelectedContract,
      manualContract,
      setManualContract,
      selectManualContract,
      rows,
      latest,
      status,
      message,
      recency: 'delayed_15m' as const,
    }),
    [contracts, latest, manualContract, message, rows, selectedContract, status],
  )
}
