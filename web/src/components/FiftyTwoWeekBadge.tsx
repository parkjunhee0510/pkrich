import type { SectorsPricePoint } from '../hooks/useSectorsData'

interface Props {
  history: SectorsPricePoint[]
}

interface Position {
  high: number
  low: number
  current: number
  pctFromHigh: number  // negative when below high
  pctFromLow: number   // positive when above low
  pctRange: number     // 0 = at low, 100 = at high
}

/**
 * 52-week high/low position indicator. Uses the full 1y close series we ship
 * in `sectors.json`. Short history (new listing, IPO within the year) falls
 * back to whatever we have -- label stays "52W" conceptually but visually it
 * simply reflects the series extent.
 */
export function FiftyTwoWeekBadge({ history }: Props) {
  const pos = computePosition(history)
  if (!pos) return null

  const tone = classifyTone(pos.pctRange)

  return (
    <div
      className={`fiftytwo-badge fiftytwo-${tone}`}
      title={[
        `현재: ${pos.current.toFixed(2)}`,
        `52W High: ${pos.high.toFixed(2)} (${pos.pctFromHigh.toFixed(1)}%)`,
        `52W Low: ${pos.low.toFixed(2)} (+${pos.pctFromLow.toFixed(1)}%)`,
        `레인지 위치: ${pos.pctRange.toFixed(0)}%`,
      ].join('\n')}
    >
      <div className="fiftytwo-scale">
        <span className="fiftytwo-scale-low">L</span>
        <div className="fiftytwo-scale-track">
          <div
            className="fiftytwo-scale-marker"
            style={{ left: `${Math.max(0, Math.min(100, pos.pctRange))}%` }}
          />
        </div>
        <span className="fiftytwo-scale-high">H</span>
      </div>
      <div className="fiftytwo-meta">
        <span className="fiftytwo-pct">{pos.pctFromHigh.toFixed(1)}% from 52W High</span>
      </div>
    </div>
  )
}

function computePosition(history: SectorsPricePoint[]): Position | null {
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

function classifyTone(pctRange: number): 'strong' | 'neutral' | 'weak' {
  if (pctRange >= 75) return 'strong'
  if (pctRange <= 25) return 'weak'
  return 'neutral'
}

// Helper for aggregating sector-level breadth on /sectors list cards.
export function countFiftyTwoStrength(
  histories: SectorsPricePoint[][],
): { strong: number; weak: number; total: number } {
  let strong = 0
  let weak = 0
  let total = 0
  for (const h of histories) {
    const p = computePosition(h)
    if (!p) continue
    total += 1
    if (p.pctRange >= 75) strong += 1
    if (p.pctRange <= 25) weak += 1
  }
  return { strong, weak, total }
}
