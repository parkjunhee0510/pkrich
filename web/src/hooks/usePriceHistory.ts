import { useEffect, useState } from 'react'
import type { PriceHistoryRow } from '../types'
import { staticRepository } from '../data/StaticJsonRepository'
import type { DashboardRepository } from '../data/DashboardRepository'

const DATA_URL = `${import.meta.env.BASE_URL}output/data/price_history.json`

function deriveRowsFromTickerHistory(historyDays: Awaited<ReturnType<DashboardRepository['loadTickerHistory']>>): PriceHistoryRow[] {
  const rows: Array<PriceHistoryRow | null> = historyDays.map((day) => {
      const tickerPayload = day.tickers?.[0]
      if (!tickerPayload) return null
      const snapshot = tickerPayload.data_snapshot ?? {}
      return {
        date: day.date,
        ticker: tickerPayload.ticker,
        price: snapshot.Price ?? 'N/A',
        daily_change: snapshot['Daily Change'] ?? 'N/A',
        market_cap: snapshot['Market Cap'] ?? 'N/A',
        trailing_pe: snapshot['Trailing P/E'] ?? 'N/A',
        eps: snapshot.EPS ?? 'N/A',
        '52w_high': snapshot['52W High'] ?? 'N/A',
        '52w_low': snapshot['52W Low'] ?? 'N/A',
        open: snapshot.Open ?? 'N/A',
        high: snapshot.High ?? 'N/A',
        low: snapshot.Low ?? 'N/A',
        close: snapshot.Close ?? 'N/A',
        volume: snapshot.Volume ?? 'N/A',
      }
    })
  return rows.filter((row): row is PriceHistoryRow => row !== null)
}

function mergeRows(primary: PriceHistoryRow[], fallback: PriceHistoryRow[]): PriceHistoryRow[] {
  const byKey = new Map<string, PriceHistoryRow>()
  for (const row of fallback) {
    byKey.set(`${row.date}:${row.ticker}`, row)
  }
  for (const row of primary) {
    byKey.set(`${row.date}:${row.ticker}`, row)
  }
  return Array.from(byKey.values()).sort((left, right) => left.date.localeCompare(right.date))
}

export function usePriceHistory(ticker?: string, repository: DashboardRepository = staticRepository) {
  const [rows, setRows] = useState<PriceHistoryRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    Promise.all([
      fetch(DATA_URL)
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          return res.json()
        })
        .catch(() => [] as PriceHistoryRow[]),
      ticker ? repository.loadTickerHistory(ticker, 0).catch(() => []) : Promise.resolve([]),
    ])
      .then(([json, historyDays]) => {
        if (cancelled) return
        const globalRows = Array.isArray(json)
          ? (ticker ? json.filter((r) => r.ticker === ticker) : json)
          : []
        if (!ticker) {
          setRows(globalRows)
          return
        }
        const shardRows = deriveRowsFromTickerHistory(historyDays)
        setRows(mergeRows(globalRows, shardRows))
      })
      .catch(() => {
        if (cancelled) return
        setRows([])
      })
      .finally(() => {
        if (cancelled) return
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [ticker, repository])

  return { rows, loading }
}
