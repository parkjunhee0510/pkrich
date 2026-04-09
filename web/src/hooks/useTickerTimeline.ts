import { useEffect, useState } from 'react'
import type { TickerTimelineEntry, TickerTimelinesData } from '../types'

const DATA_URL = `${import.meta.env.BASE_URL}output/data/ticker_timelines.json`

export function useTickerTimeline(ticker?: string) {
  const [entries, setEntries] = useState<TickerTimelineEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(DATA_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((json: TickerTimelinesData) => {
        if (ticker) {
          setEntries(json[ticker] ?? [])
        } else {
          setEntries([])
        }
      })
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))
  }, [ticker])

  return { entries, loading }
}
