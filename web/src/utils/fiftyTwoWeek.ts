import type { SectorsPricePoint } from '../hooks/useSectorsData'

export interface FiftyTwoWeekPosition {
  high: number
  low: number
  current: number
  pctFromHigh: number
  pctFromLow: number
  pctRange: number
}

export function computeFiftyTwoWeekPosition(history: SectorsPricePoint[]): FiftyTwoWeekPosition | null {
  if (history.length < 2) return null
  const closes = history.map((p) => p.close).filter((c) => Number.isFinite(c) && c > 0)
  if (closes.length < 2) return null
  const high = Math.max(...closes)
  const low = Math.min(...closes)
  const current = closes[closes.length - 1]
  if (high <= low) return null
  const pctFromHigh = ((current - high) / high) * 100
  const pctFromLow = ((current - low) / low) * 100
  const pctRange = ((current - low) / (high - low)) * 100
  return { high, low, current, pctFromHigh, pctFromLow, pctRange }
}

export function countFiftyTwoStrength(
  histories: SectorsPricePoint[][],
): { strong: number; weak: number; total: number } {
  let strong = 0
  let weak = 0
  let total = 0
  for (const h of histories) {
    const p = computeFiftyTwoWeekPosition(h)
    if (!p) continue
    total += 1
    if (p.pctRange >= 75) strong += 1
    if (p.pctRange <= 25) weak += 1
  }
  return { strong, weak, total }
}
