import { useCallback, useEffect, useRef, useState } from 'react'
import type { DashboardRepository } from '../data/DashboardRepository'
import { staticRepository } from '../data/StaticJsonRepository'
import type { DashboardData } from '../types'

type UseDashboardDataOptions = {
  pollIntervalMs?: number
  repository?: DashboardRepository
}

export function useDashboardData(options: UseDashboardDataOptions = {}) {
  const { pollIntervalMs = 0, repository = staticRepository } = options
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState(0)
  const hasLoadedRef = useRef(false)

  const refresh = useCallback(() => {
    setError(null)
    setRefreshing(true)
    setRefreshToken((current) => current + 1)
  }, [])

  useEffect(() => {
    let cancelled = false

    repository
      .loadDashboard(refreshToken)
      .then((payload) => {
        if (cancelled) return
        setData(payload)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (cancelled) return
        if (!hasLoadedRef.current) {
          hasLoadedRef.current = true
          setLoading(false)
        }
        setRefreshing(false)
      })

    return () => {
      cancelled = true
    }
  }, [refreshToken, repository])

  useEffect(() => {
    if (pollIntervalMs <= 0) return
    const timer = window.setInterval(() => {
      setRefreshToken((current) => current + 1)
    }, pollIntervalMs)
    return () => window.clearInterval(timer)
  }, [pollIntervalMs])

  return { data, loading, refreshing, error, refresh }
}
