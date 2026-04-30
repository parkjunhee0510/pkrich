import { useEffect, useState } from 'react'
import type { TickerAnalysisData } from '../types'
import { staticRepository } from '../data/StaticJsonRepository'
import type { DashboardRepository } from '../data/DashboardRepository'

type Status = 'idle' | 'loading' | 'loaded' | 'missing' | 'error'

export function useTickerAnalysis(
  ticker: string | undefined,
  repository: DashboardRepository = staticRepository,
  pollIntervalMs: number = 0,
) {
  const [analysis, setAnalysis] = useState<TickerAnalysisData | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState(0)

  useEffect(() => {
    let cancelled = false

    async function loadAnalysis() {
      if (!ticker) {
        setStatus('idle')
        setAnalysis(null)
        return
      }

      setStatus('loading')
      setError(null)
      try {
        const payload = await repository.loadTickerLatest(ticker, refreshToken)
        if (cancelled) return
        if (payload) {
          setAnalysis(payload)
          setStatus('loaded')
        } else {
          setAnalysis(null)
          setStatus('missing')
        }
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
        setStatus('error')
      }
    }

    void loadAnalysis()

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
    analysis,
    loading: status === 'loading' || status === 'idle',
    missing: status === 'missing',
    error,
  }
}
