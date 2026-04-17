import { useEffect, useState } from 'react'
import type { DailyEntry } from '../types'
import { staticRepository } from '../data/StaticJsonRepository'
import type { DashboardRepository } from '../data/DashboardRepository'

type Status = 'idle' | 'loading' | 'loaded' | 'error'

export function useTickerHistory(
  ticker: string | undefined,
  repository: DashboardRepository = staticRepository,
  pollIntervalMs: number = 0,
) {
  const [history, setHistory] = useState<DailyEntry[]>([])
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState(0)

  useEffect(() => {
    if (!ticker) {
      setStatus('idle')
      setHistory([])
      return
    }
    let cancelled = false
    setStatus('loading')
    setError(null)
    repository
      .loadTickerHistory(ticker, refreshToken)
      .then((payload) => {
        if (cancelled) return
        setHistory(payload)
        setStatus('loaded')
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
        setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [ticker, repository, refreshToken])

  useEffect(() => {
    if (!ticker || pollIntervalMs <= 0) {
      return
    }
    const timer = window.setInterval(() => {
      setRefreshToken((current) => current + 1)
    }, pollIntervalMs)
    return () => window.clearInterval(timer)
  }, [ticker, pollIntervalMs])

  return {
    history,
    loading: status === 'loading' || status === 'idle',
    error,
  }
}
