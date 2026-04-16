import { useCallback, useEffect, useRef, useState } from 'react'
import type { DashboardData } from '../types'

const DATA_URL = `${import.meta.env.BASE_URL}output/data/dashboard.json`
const HISTORY_URL = `${import.meta.env.BASE_URL}output/data/dashboard_history.json`

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
    Promise.all([
      fetch(`${DATA_URL}?ts=${refreshToken}`, { cache: 'no-store' }).then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      }),
      fetch(`${HISTORY_URL}?ts=${refreshToken}`, { cache: 'no-store' })
        .then((res) => (res.ok ? res.json() : null))
        .catch(() => null),
    ])
      .then(([latestJson, historyJson]: [DashboardData, DashboardData | null]) => {
        const latestDays = Array.isArray(latestJson?.days) ? latestJson.days : []
        const historyDays = Array.isArray(historyJson?.days) ? historyJson.days : []

        // historyDays를 base로 하되, latestDays의 각 날짜를 upsert하여
        // signal_history 등 최신 필드가 유실되지 않도록 함
        let mergedDays = latestDays
        if (historyDays.length > 0) {
          const latestDaysByDate = new Map(latestDays.map((d) => [d.date, d]))
          mergedDays = [
            ...historyDays.filter((d) => !latestDaysByDate.has(d.date)),
            ...latestDays,
          ].sort((a, b) => a.date.localeCompare(b.date))
        }

        setData({
          ...latestJson,
          days: mergedDays,
        })
      })
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
