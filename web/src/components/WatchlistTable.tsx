import { Link } from 'react-router-dom'
import type { TickerAnalysisData } from '../types'
import { parseNumericChange, changeColor } from '../utils/format'
import { SignalBadge } from './SignalBadge'
import { TickerMetaStack } from './TraderDashboardPanels'
import { buildDashboardPositioningSummary, buildPositionSizingSummary, computeSetupScore, extractActionPlan } from '../utils/trader'

export function WatchlistTable({
  tickers,
  accountSize,
}: {
  tickers: TickerAnalysisData[]
  accountSize: number
}) {
  return (
    <div className="table-wrap">
      <table className="watchlist-table">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Setup</th>
            <th>Name</th>
            <th>Price</th>
            <th>Change</th>
            <th>7D</th>
            <th>30D</th>
            <th>Action Bar</th>
            <th>Positioning</th>
            <th>Sizing</th>
            <th>Signal</th>
          </tr>
        </thead>
        <tbody>
          {tickers.map((ticker) => {
            const pct = parseNumericChange(ticker.data_snapshot['Daily Change'] ?? '0')
            const setup = computeSetupScore(ticker)
            const positioningSummary = buildDashboardPositioningSummary(ticker)
            const sizingSummary = buildPositionSizingSummary(ticker, accountSize)
            const actionPlan = extractActionPlan(ticker)

            return (
              <tr key={ticker.ticker}>
                <td>
                  <Link to={`/ticker/${ticker.ticker}`} className="ticker-link">{ticker.ticker}</Link>
                </td>
                <td className="setup-cell">
                  <div className="setup-cell-score">{setup.score}</div>
                  <div className="setup-cell-focus">{setup.focusLabel}</div>
                </td>
                <td className="name-cell">
                  <TickerMetaStack ticker={ticker} />
                </td>
                <td>{ticker.data_snapshot['Price']}</td>
                <td style={{ color: changeColor(pct), fontWeight: 600 }}>
                  {ticker.data_snapshot['Daily Change']}
                </td>
                <td>{ticker.period_changes?.['7d'] ?? 'N/A'}</td>
                <td>{ticker.period_changes?.['30d'] ?? 'N/A'}</td>
                <td className="action-bar-cell">
                  <strong>{actionPlan.direction}</strong>
                  <span>{actionPlan.thesis}</span>
                  <span>진입존 {actionPlan.entry}</span>
                  <span>무효화 {actionPlan.invalidation}</span>
                  <span>다음 촉매 {actionPlan.nextCatalyst}</span>
                </td>
                <td className="positioning-cell">{positioningSummary}</td>
                <td className="sizing-cell">
                  <strong>{sizingSummary.stopPrice}</strong>
                  <span>{sizingSummary.positionShares}</span>
                  <span>{sizingSummary.riskReward}</span>
                </td>
                <td><SignalBadge changePercent={pct} /></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
