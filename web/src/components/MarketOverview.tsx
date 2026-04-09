import type { MarketOverviewEntry } from '../types'
import { parseNumericChange, changeColor } from '../utils/format'

export function MarketOverview({ entries }: { entries: MarketOverviewEntry[] }) {
  if (!entries.length) return null

  return (
    <div className="market-overview">
      {entries.map((e) => {
        const pct = parseNumericChange(e.change)
        return (
          <div key={e.symbol} className="market-overview-item">
            <span className="market-label">{e.label}</span>
            <span className="market-price">{e.price}</span>
            <span style={{ color: changeColor(pct) }}>{e.change}</span>
          </div>
        )
      })}
    </div>
  )
}
