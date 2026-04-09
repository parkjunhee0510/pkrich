import { useEffect, useState } from 'react'
import type { PriceHistoryRow } from '../types'

const DATA_URL = `${import.meta.env.BASE_URL}output/data/price_history.json`

export function usePriceHistory(ticker?: string) {
  const [rows, setRows] = useState<PriceHistoryRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(DATA_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((json: PriceHistoryRow[]) => {
        if (ticker) {
          setRows(json.filter((r) => r.ticker === ticker))
        } else {
          setRows(json)
        }
      })
      .catch(() => setRows([]))
      .finally(() => setLoading(false))
  }, [ticker])

  return { rows, loading }
}
