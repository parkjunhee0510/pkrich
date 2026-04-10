import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useDashboardData } from '../hooks/useDashboardData'
import { TablePageSkeleton } from '../components/Skeleton'
import { ErrorState } from '../components/ErrorState'
import type { SignalHistoryRow, SignalDirectionSummary } from '../types'
import { changeColor } from '../utils/format'

const DIRECTION_LABELS: Record<string, string> = {
  bull: '강세',
  bear: '약세',
  neutral: '중립',
}

const DIRECTION_COLORS: Record<string, string> = {
  bull: 'var(--color-up)',
  bear: 'var(--color-down)',
  neutral: 'var(--color-neutral)',
}

function formatReturn(value: string): { text: string; color: string } {
  if (!value || value === 'N/A' || value === '') return { text: '-', color: 'var(--color-text-secondary)' }
  const num = parseFloat(value)
  if (isNaN(num)) return { text: value, color: 'var(--color-text-secondary)' }
  const text = `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`
  const color = changeColor(num)
  return { text, color }
}

function SummaryCard({ direction, summary }: { direction: string; summary: SignalDirectionSummary }) {
  const winRate = summary.win_rate_5d && summary.win_rate_5d !== 'N/A' ? summary.win_rate_5d : '-'
  const avgReturn = formatReturn(summary.avg_return_5d)

  return (
    <div className="signal-summary-card">
      <div className="signal-summary-direction" style={{ color: DIRECTION_COLORS[direction] ?? 'var(--color-text)' }}>
        {DIRECTION_LABELS[direction] ?? direction}
      </div>
      <div className="signal-summary-count">{summary.count}건</div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">평가 완료</span>
        <span>{summary.evaluated_5d}건</span>
      </div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">5일 승률</span>
        <span style={{ fontWeight: 700 }}>{winRate}</span>
      </div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">5일 평균</span>
        <span style={{ color: avgReturn.color, fontWeight: 600 }}>{avgReturn.text}</span>
      </div>
    </div>
  )
}

function SignalRow({ signal }: { signal: SignalHistoryRow }) {
  const r1d = formatReturn(signal.return_1d)
  const r5d = formatReturn(signal.return_5d)
  const r20d = formatReturn(signal.return_20d)

  return (
    <tr>
      <td>{signal.signal_date}</td>
      <td>
        <Link to={`/ticker/${signal.ticker}`} className="ticker-link">
          {signal.ticker}
        </Link>
      </td>
      <td>
        <span
          className="signal-direction-chip"
          style={{ color: DIRECTION_COLORS[signal.signal_direction] ?? 'inherit' }}
        >
          {DIRECTION_LABELS[signal.signal_direction] ?? signal.signal_direction}
        </span>
      </td>
      <td style={{ textAlign: 'right' }}>${signal.signal_price}</td>
      <td className="catalyst-cell">{signal.catalyst_tag || '-'}</td>
      <td style={{ textAlign: 'right', color: r1d.color }}>{r1d.text}</td>
      <td style={{ textAlign: 'right', color: r5d.color }}>{r5d.text}</td>
      <td style={{ textAlign: 'right', color: r20d.color }}>{r20d.text}</td>
    </tr>
  )
}

export function Signals() {
  const { data, loading, error } = useDashboardData()
  const [directionFilter, setDirectionFilter] = useState<string>('ALL')
  const [tickerFilter, setTickerFilter] = useState('')

  useEffect(() => {
    document.title = '시그널 검증 · Stock Research'
  }, [])

  if (loading) return <TablePageSkeleton title="시그널 검증 통계" />
  if (error) return <ErrorState message={error} />
  if (!data) return <p className="status">No data available.</p>

  const signalStats = data.signal_stats
  if (!signalStats || !signalStats.recent_signals || signalStats.recent_signals.length === 0) {
    return (
      <div className="signals-page">
        <h2>시그널 검증 통계</h2>
        <p className="status">시그널 데이터가 아직 축적되지 않았습니다. 파이프라인이 수일간 실행되면 자동으로 채워집니다.</p>
      </div>
    )
  }

  const summaryEntries = Object.entries(signalStats.summary_by_direction ?? {})
  const normalizedTickerFilter = tickerFilter.trim().toUpperCase()

  const filteredSignals = signalStats.recent_signals.filter((s) => {
    const matchDirection = directionFilter === 'ALL' || s.signal_direction === directionFilter
    const matchTicker = normalizedTickerFilter.length === 0 || s.ticker.includes(normalizedTickerFilter)
    return matchDirection && matchTicker
  })

  // Compute overall stats
  const evaluated5d = signalStats.recent_signals.filter((s) => s.evaluated_5d === 'True')
  const totalEval = evaluated5d.length
  const wins5d = evaluated5d.filter((s) => {
    const ret = parseFloat(s.return_5d)
    if (isNaN(ret)) return false
    return s.signal_direction === 'bull' ? ret > 0 : s.signal_direction === 'bear' ? ret < 0 : false
  }).length
  const overallWinRate = totalEval > 0 ? ((wins5d / totalEval) * 100).toFixed(1) : '-'
  const catalystEntries = Object.entries(signalStats.meta_analysis?.by_catalyst_tag ?? {}).slice(0, 6)

  return (
    <div className="signals-page">
      <div className="dashboard-header">
        <h2>시그널 검증 통계</h2>
        <div className="signal-overall-badge">
          전체 5일 승률: <strong>{overallWinRate}%</strong> ({wins5d}/{totalEval})
        </div>
      </div>

      {/* Direction Summary Cards */}
      {summaryEntries.length > 0 && (
        <div className="signal-summary-grid">
          {summaryEntries.map(([dir, summary]) => (
            <SummaryCard key={dir} direction={dir} summary={summary} />
          ))}
        </div>
      )}

      {catalystEntries.length > 0 && (
        <section className="signals-meta-section">
          <div className="section-header-with-kicker">
            <div>
              <h3>촉매 유형별 성과</h3>
              <p className="section-kicker">5일 평가 완료 시그널 기준으로 가장 자주 등장한 촉매를 비교합니다.</p>
            </div>
          </div>
          <div className="signal-summary-grid">
            {catalystEntries.map(([tag, summary]) => (
              <div key={tag} className="signal-summary-card">
                <div className="signal-summary-direction">{tag}</div>
                <div className="signal-summary-count">{summary.count}건</div>
                <div className="signal-summary-row">
                  <span className="signal-summary-label">평균 수익률</span>
                  <span>{summary.avg_return}</span>
                </div>
                <div className="signal-summary-row">
                  <span className="signal-summary-label">승률</span>
                  <span>{summary.win_rate}</span>
                </div>
                <div className="signal-summary-row">
                  <span className="signal-summary-label">최고 / 최저</span>
                  <span>{summary.best} / {summary.worst}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Filters */}
      <div className="dashboard-controls" style={{ marginTop: '1.5rem' }}>
        <input
          className="dashboard-search"
          type="search"
          placeholder="티커 검색"
          value={tickerFilter}
          onChange={(e) => setTickerFilter(e.target.value)}
        />
        <select
          className="dashboard-filter"
          value={directionFilter}
          onChange={(e) => setDirectionFilter(e.target.value)}
        >
          <option value="ALL">전체 방향</option>
          <option value="bull">강세</option>
          <option value="bear">약세</option>
          <option value="neutral">중립</option>
        </select>
      </div>

      {/* Signal History Table */}
      <div className="table-wrap">
        <table className="watchlist-table">
          <thead>
            <tr>
              <th>날짜</th>
              <th>종목</th>
              <th>방향</th>
              <th style={{ textAlign: 'right' }}>시그널가</th>
              <th>촉매</th>
              <th style={{ textAlign: 'right' }}>1D</th>
              <th style={{ textAlign: 'right' }}>5D</th>
              <th style={{ textAlign: 'right' }}>20D</th>
            </tr>
          </thead>
          <tbody>
            {filteredSignals.length > 0 ? (
              filteredSignals.map((signal, idx) => <SignalRow key={`${signal.signal_date}-${signal.ticker}-${idx}`} signal={signal} />)
            ) : (
              <tr>
                <td colSpan={8} className="status">조건에 맞는 시그널이 없습니다.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
