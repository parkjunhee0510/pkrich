import { Link } from 'react-router-dom'
import type { TickerAnalysisData } from '../types'
import { parseNumericChange, changeColor } from '../utils/format'
import { SignalBadge } from './SignalBadge'
import { SecFilingBadges } from './SecFilingBadges'

export function WatchlistTable({ tickers }: { tickers: TickerAnalysisData[] }) {
  return (
    <div className="table-wrap">
      <table className="watchlist-table">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Name</th>
            <th>Price</th>
            <th>Change</th>
            <th>7D</th>
            <th>30D</th>
            <th>Signal</th>
            <th>Takeaway</th>
          </tr>
        </thead>
        <tbody>
          {tickers.map((t) => {
            const pct = parseNumericChange(t.data_snapshot['Daily Change'] ?? '0')
            return (
              <tr key={t.ticker}>
                <td>
                  <Link to={`/ticker/${t.ticker}`} className="ticker-link">{t.ticker}</Link>
                </td>
                <td className="name-cell">
                  <div>{t.name}</div>
                  <SecFilingBadges tags={t.sec_filing_tags} />
                  {t.upcoming_events.length > 0 && (
                    <div className="event-badges">
                      {t.upcoming_events.slice(0, 2).map((event) => (
                        <span key={`${event.type}-${event.date}`} className="event-badge">
                          {event.label} D-{event.days_until}
                        </span>
                      ))}
                    </div>
                  )}
                </td>
                <td>{t.data_snapshot['Price']}</td>
                <td style={{ color: changeColor(pct), fontWeight: 600 }}>
                  {t.data_snapshot['Daily Change']}
                </td>
                <td>{t.period_changes?.['7d'] ?? 'N/A'}</td>
                <td>{t.period_changes?.['30d'] ?? 'N/A'}</td>
                <td><SignalBadge changePercent={pct} /></td>
                <td className="takeaway-cell">{t.signal_or_takeaway}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
