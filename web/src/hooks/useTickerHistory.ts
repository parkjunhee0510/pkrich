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
    let cancelled = false

    async function loadHistory() {
      if (!ticker) {
        setStatus('idle')
        setHistory([])
        return
      }

      setStatus('loading')
      setError(null)
      try {
        const payload = await repository.loadTickerHistory(ticker, refreshToken)
        if (cancelled) return
        setHistory(payload)
        setStatus('loaded')
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
        setStatus('error')
      }
    }

    void loadHistory()

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
