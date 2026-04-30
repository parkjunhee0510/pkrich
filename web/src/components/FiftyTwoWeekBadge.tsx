import type { SectorsPricePoint } from '../hooks/useSectorsData'
import { computeFiftyTwoWeekPosition } from '../utils/fiftyTwoWeek'

interface Props {
  history: SectorsPricePoint[]
}

/**
 * 52-week high/low position indicator. Uses the full 1y close series we ship
 * in `sectors.json`. Short history (new listing, IPO within the year) falls
 * back to whatever we have -- label stays "52W" conceptually but visually it
 * simply reflects the series extent.
 */
export function FiftyTwoWeekBadge({ history }: Props) {
  const pos = computeFiftyTwoWeekPosition(history)
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

function classifyTone(pctRange: number): 'strong' | 'neutral' | 'weak' {
  if (pctRange >= 75) return 'strong'
  if (pctRange <= 25) return 'weak'
  return 'neutral'
}
