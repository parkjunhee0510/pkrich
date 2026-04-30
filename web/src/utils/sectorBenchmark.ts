import type { SectorsPricePoint } from '../hooks/useSectorsData'

/**
 * Ticker vs benchmark relative return over the given lookback.
 * Returns null when either series is too short.
 */
export function relativeReturn(
  tickerHistory: SectorsPricePoint[],
  benchmarkHistory: SectorsPricePoint[],
  lookback: number,
): { ticker: number; benchmark: number; relative: number } | null {
  const t = windowReturn(tickerHistory, lookback)
  const b = windowReturn(benchmarkHistory, lookback)
  if (t === null || b === null) return null
  return { ticker: t, benchmark: b, relative: t - b }
}

export function windowReturn(history: SectorsPricePoint[], lookback: number): number | null {
  if (history.length < 2) return null
  const last = history[history.length - 1]?.close
  const startIdx = lookback < 0
    ? 0
    : Math.max(0, history.length - 1 - lookback)
  const start = history[startIdx]?.close
  if (!last || !start) return null
  return ((last - start) / start) * 100
}
