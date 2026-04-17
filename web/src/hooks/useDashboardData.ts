import { useCallback, useEffect, useRef, useState } from 'react'
import type { DashboardData } from '../types'
import { staticRepository } from '../data/StaticJsonRepository'
import type { DashboardRepository } from '../data/DashboardRepository'

interface Options {
  enabled?: boolean
  repository?: DashboardRepository
  pollIntervalMs?: number
}

export function useDashboardData(options: Options = {}) {
  const { enabled = true, repository = staticRepository, pollIntervalMs = 0 } = options
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(enabled)
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
    if (!enabled) {
      setLoading(false)
      return
    }
    repository
      .loadDashboard(refreshToken)
      .then((merged) => setData(merged))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => {
        if (!hasLoadedRef.current) {
          hasLoadedRef.current = true
          setLoading(false)
        }
        setRefreshing(false)
      })
  }, [refreshToken, repository, enabled])

  useEffect(() => {
    if (!enabled || pollIntervalMs <= 0) {
      return
    }
    const timer = window.setInterval(() => {
      setRefreshToken((current) => current + 1)
    }, pollIntervalMs)
    return () => window.clearInterval(timer)
  }, [enabled, pollIntervalMs])

  return { data, loading, refreshing, error, refresh }
}
