import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useDashboardData } from '../hooks/useDashboardData'
import { TablePageSkeleton } from '../components/Skeleton'
import { ErrorState } from '../components/ErrorState'
import type { PortfolioSummaryData } from '../types'
import { parseNumericChange, changeColor } from '../utils/format'

function formatCurrency(value: number, currency = 'USD'): string {
  return `${currency === 'KRW' ? '₩' : '$'}${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function pnlColor(value: number): string {
  if (value > 0) return 'var(--color-up)'
  if (value < 0) return 'var(--color-down)'
  return 'var(--color-neutral)'
}

export function Portfolio() {
  const { data, loading, error } = useDashboardData()

  useEffect(() => {
    document.title = '포트폴리오 · Stock Research'
  }, [])

  if (loading) return <TablePageSkeleton title="포트폴리오" />
  if (error) return <ErrorState message={error} />
  if (!data || data.days.length === 0) return <p className="status">No data available.</p>

  const latestDay = data.days[data.days.length - 1]
  const portfolioRaw = latestDay.portfolio_summary as PortfolioSummaryData | null | undefined

  if (!portfolioRaw || !portfolioRaw.positions || portfolioRaw.positions.length === 0) {
    return (
      <div className="portfolio-page">
        <h2>포트폴리오</h2>
        <p className="status">
          포트폴리오 데이터가 없습니다. <code>watchlist.yaml</code>에 보유 종목을 설정해 주세요.
        </p>
      </div>
    )
  }

  const portfolio = portfolioRaw
  const sortedPositions = [...portfolio.positions].sort(
    (a, b) => Math.abs(b.unrealized_pnl) - Math.abs(a.unrealized_pnl),
  )

  const winCount = portfolio.positions.filter((p) => p.unrealized_pnl > 0).length
  const lossCount = portfolio.positions.filter((p) => p.unrealized_pnl < 0).length

  return (
    <div className="portfolio-page">
      <div className="dashboard-header">
        <h2>포트폴리오 · {latestDay.date}</h2>
      </div>

      {/* Summary Cards */}
      <div className="portfolio-summary-grid">
        <div className="portfolio-summary-card">
          <div className="portfolio-card-label">평가금액</div>
          <div className="portfolio-card-value">{formatCurrency(portfolio.total_market_value)}</div>
        </div>
        <div className="portfolio-summary-card">
          <div className="portfolio-card-label">투자원금</div>
          <div className="portfolio-card-value">{formatCurrency(portfolio.total_cost_basis)}</div>
        </div>
        <div className="portfolio-summary-card">
          <div className="portfolio-card-label">미실현 손익</div>
          <div className="portfolio-card-value" style={{ color: pnlColor(portfolio.total_unrealized_pnl) }}>
            {portfolio.total_unrealized_pnl >= 0 ? '+' : ''}{formatCurrency(portfolio.total_unrealized_pnl)}
          </div>
          <div className="portfolio-card-sub" style={{ color: pnlColor(portfolio.total_unrealized_return_pct) }}>
            {portfolio.total_unrealized_return_pct >= 0 ? '+' : ''}{portfolio.total_unrealized_return_pct.toFixed(2)}%
          </div>
        </div>
        <div className="portfolio-summary-card">
          <div className="portfolio-card-label">승/패</div>
          <div className="portfolio-card-value">
            <span style={{ color: 'var(--color-up)' }}>{winCount}W</span>
            {' / '}
            <span style={{ color: 'var(--color-down)' }}>{lossCount}L</span>
          </div>
        </div>
      </div>

      {/* Positions Table */}
      <div className="table-wrap">
        <table className="watchlist-table">
          <thead>
            <tr>
              <th>종목</th>
              <th style={{ textAlign: 'right' }}>수량</th>
              <th style={{ textAlign: 'right' }}>평균단가</th>
              <th style={{ textAlign: 'right' }}>현재가</th>
              <th style={{ textAlign: 'right' }}>평가금액</th>
              <th style={{ textAlign: 'right' }}>손익</th>
              <th style={{ textAlign: 'right' }}>수익률</th>
              <th>시그널</th>
            </tr>
          </thead>
          <tbody>
            {sortedPositions.map((pos) => {
              const tickerAnalysis = latestDay.tickers.find((t) => t.ticker === pos.ticker)
              const dailyChange = tickerAnalysis
                ? parseNumericChange(tickerAnalysis.data_snapshot['Daily Change'] ?? '0')
                : null
              return (
                <tr key={pos.ticker}>
                  <td>
                    <Link to={`/ticker/${pos.ticker}`} className="ticker-link">
                      {pos.ticker}
                    </Link>
                  </td>
                  <td style={{ textAlign: 'right' }}>{pos.shares}</td>
                  <td style={{ textAlign: 'right' }}>{formatCurrency(pos.avg_cost, pos.currency)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <span>{formatCurrency(pos.market_price, pos.currency)}</span>
                    {dailyChange !== null && (
                      <span style={{ color: changeColor(dailyChange), fontSize: '0.8rem', marginLeft: '0.4rem' }}>
                        {dailyChange >= 0 ? '+' : ''}{dailyChange.toFixed(2)}%
                      </span>
                    )}
                  </td>
                  <td style={{ textAlign: 'right' }}>{formatCurrency(pos.market_value, pos.currency)}</td>
                  <td style={{ textAlign: 'right', color: pnlColor(pos.unrealized_pnl) }}>
                    {pos.unrealized_pnl >= 0 ? '+' : ''}{formatCurrency(pos.unrealized_pnl, pos.currency)}
                  </td>
                  <td style={{ textAlign: 'right', color: pnlColor(pos.unrealized_return_pct) }}>
                    {pos.unrealized_return_pct >= 0 ? '+' : ''}{pos.unrealized_return_pct.toFixed(2)}%
                  </td>
                  <td className="takeaway-cell">
                    {tickerAnalysis?.signal_or_takeaway ?? '-'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
