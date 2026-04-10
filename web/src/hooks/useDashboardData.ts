import { useCallback, useEffect, useRef, useState } from 'react'
import type { DashboardData } from '../types'

const DATA_URL = `${import.meta.env.BASE_URL}output/data/dashboard.json`

export function useDashboardData() {
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
    fetch(`${DATA_URL}?ts=${refreshToken}`, { cache: 'no-store' })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((json: DashboardData) => setData(json))
      .catch((err) => setError(err.message))
      .finally(() => {
        if (!hasLoadedRef.current) {
          hasLoadedRef.current = true
          setLoading(false)
        }
        setRefreshing(false)
      })
  }, [refreshToken])

  return { data, loading, refreshing, error, refresh }
}
