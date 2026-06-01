import { useCallback, useEffect, useRef, useState } from 'react'
import type { DashboardRepository } from '../data/DashboardRepository'
import { staticRepository } from '../data/StaticJsonRepository'
import type { DashboardData } from '../types'

type DashboardInFlightRequest = {
  refreshToken: number
  promise: Promise<DashboardData>
}

const dashboardDataCache = new WeakMap<DashboardRepository, DashboardData>()
const dashboardRequestCache = new WeakMap<DashboardRepository, DashboardInFlightRequest>()

type UseDashboardDataOptions = {
  pollIntervalMs?: number
  repository?: DashboardRepository
}

function loadDashboardWithCache(repository: DashboardRepository, refreshToken: number) {
  const inFlight = dashboardRequestCache.get(repository)
  if (inFlight?.refreshToken === refreshToken) {
    return inFlight.promise
  }

  const promise = repository
    .loadDashboard(refreshToken)
    .then((payload) => {
      dashboardDataCache.set(repository, payload)
      dashboardRequestCache.delete(repository)
      return payload
    })
    .catch((error: unknown) => {
      dashboardRequestCache.delete(repository)
      throw error
    })

  dashboardRequestCache.set(repository, { refreshToken, promise })
  return promise
}

export function useDashboardData(options: UseDashboardDataOptions = {}) {
  const { pollIntervalMs = 0, repository = staticRepository } = options
  const cachedDashboardData = dashboardDataCache.get(repository)
  const [data, setData] = useState<DashboardData | null>(() => cachedDashboardData ?? null)
  const [loading, setLoading] = useState(() => !cachedDashboardData)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState(0)
  const hasLoadedRef = useRef(Boolean(cachedDashboardData))

  const refresh = useCallback(() => {
    setError(null)
    setRefreshing(true)
    setRefreshToken((current) => current + 1)
  }, [])

  useEffect(() => {
    let cancelled = false

    loadDashboardWithCache(repository, refreshToken)
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
