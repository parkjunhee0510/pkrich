import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { PriceHistoryRow } from '../types'
import { parseNumericChange, parsePrice } from '../utils/format'

const DATA_URL = `${import.meta.env.BASE_URL}output/data/price_history.json`
const POLL_INTERVAL_MS = 30_000

export interface PriceHistoryTickerSummary {
  ticker: string
  latestPrice: string
  latestChange: string
  latestDate: string
}

function buildTickerSummaries(rows: PriceHistoryRow[]): PriceHistoryTickerSummary[] {
  const latestByTicker = new Map<string, PriceHistoryRow>()
  for (const row of rows) {
    const existing = latestByTicker.get(row.ticker)
    if (!existing || row.date > existing.date) {
      latestByTicker.set(row.ticker, row)
    }
  }

  return Array.from(latestByTicker.values())
    .map((row) => ({
      ticker: row.ticker,
      latestPrice: row.price ?? 'N/A',
      latestChange: row.daily_change ?? 'N/A',
      latestDate: row.date,
    }))
    .sort((left, right) => {
      const dateCompare = right.latestDate.localeCompare(left.latestDate)
      if (dateCompare !== 0) return dateCompare
      const changeCompare = parseNumericChange(right.latestChange) - parseNumericChange(left.latestChange)
      if (changeCompare !== 0) return changeCompare
      return parsePrice(right.latestPrice) - parsePrice(left.latestPrice)
    })
}

export function usePriceHistoryLive() {
  const [allRows, setAllRows] = useState<PriceHistoryRow[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const signatureRef = useRef('')
  const hasLoadedRef = useRef(false)

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`${DATA_URL}?ts=${Date.now()}`, { cache: 'no-store' })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const json = await response.json() as PriceHistoryRow[]
      const nextRows = Array.isArray(json) ? json : []
      const nextSignature = JSON.stringify(nextRows)
      if (signatureRef.current !== nextSignature) {
        signatureRef.current = nextSignature
        setAllRows(nextRows)
      }
      setLastUpdated(new Date().toISOString())
    } catch {
      if (signatureRef.current === '') {
        setAllRows([])
      }
    } finally {
      if (!hasLoadedRef.current) {
        hasLoadedRef.current = true
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    let intervalId: number | null = null

    const stopPolling = () => {
      if (intervalId !== null) {
        window.clearInterval(intervalId)
        intervalId = null
      }
    }

    const startPolling = () => {
      if (intervalId !== null) return
      intervalId = window.setInterval(() => {
        if (document.visibilityState === 'visible') {
          void refresh()
        }
      }, POLL_INTERVAL_MS)
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void refresh()
        startPolling()
      } else {
        stopPolling()
      }
    }

    void refresh()
    if (document.visibilityState === 'visible') {
      startPolling()
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      stopPolling()
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [refresh])

  const tickers = useMemo(() => buildTickerSummaries(allRows), [allRows])

  return {
    allRows,
    tickers,
    loading,
    lastUpdated,
    refresh,
  }
}
