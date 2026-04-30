import { useState, useEffect, useMemo } from 'react'
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

interface TickerStats {
  ticker: string
  count: number
  evaluated: number
  wins: number
  avgReturn: number | null
  bullCount: number
  bearCount: number
}

function computeTickerStats(signals: SignalHistoryRow[]): TickerStats[] {
  const map = new Map<string, TickerStats>()

  for (const s of signals) {
    if (!map.has(s.ticker)) {
      map.set(s.ticker, { ticker: s.ticker, count: 0, evaluated: 0, wins: 0, avgReturn: null, bullCount: 0, bearCount: 0 })
    }
    const stat = map.get(s.ticker)!
    stat.count++
    if (s.signal_direction === 'bull') stat.bullCount++
    if (s.signal_direction === 'bear') stat.bearCount++

    const ret = parseFloat(s.return_5d)
    if (s.evaluated_5d === 'True' && !isNaN(ret)) {
      stat.evaluated++
      const isWin = s.signal_direction === 'bull' ? ret > 0 : s.signal_direction === 'bear' ? ret < 0 : false
      if (isWin) stat.wins++
      stat.avgReturn = stat.avgReturn === null ? ret : (stat.avgReturn * (stat.evaluated - 1) + ret) / stat.evaluated
    }
  }

  return Array.from(map.values()).sort((a, b) => b.count - a.count)
}

function TickerSummaryCard({ stat }: { stat: TickerStats }) {
  const winRate = stat.evaluated > 0 ? `${((stat.wins / stat.evaluated) * 100).toFixed(1)}%` : '-'
  const avgRet = stat.avgReturn !== null ? formatReturn(stat.avgReturn.toFixed(2)) : { text: '-', color: 'var(--color-text-secondary)' }

  return (
    <div className="signal-summary-card">
      <div className="signal-summary-direction">
        <Link to={`/ticker/${stat.ticker}`} style={{ color: 'var(--color-accent)', textDecoration: 'none', fontWeight: 700 }}>
          {stat.ticker}
        </Link>
      </div>
      <div className="signal-summary-count">{stat.count}건</div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">강세 / 약세</span>
        <span style={{ color: 'var(--color-up)' }}>{stat.bullCount}</span>
        <span style={{ margin: '0 4px', color: 'var(--color-text-secondary)' }}>/</span>
        <span style={{ color: 'var(--color-down)' }}>{stat.bearCount}</span>
      </div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">5일 승률</span>
        <span style={{ fontWeight: 700 }}>{winRate}</span>
      </div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">5일 평균</span>
        <span style={{ color: avgRet.color, fontWeight: 600 }}>{avgRet.text}</span>
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

function GroupedSignalRows({ ticker, signals }: { ticker: string; signals: SignalHistoryRow[] }) {
  return (
    <>
      <tr className="ticker-group-header-row">
        <td colSpan={8}>
          <Link to={`/ticker/${ticker}`} className="ticker-link" style={{ fontWeight: 700, fontSize: '0.85rem' }}>
            {ticker}
          </Link>
          <span style={{ marginLeft: '0.5rem', color: 'var(--color-text-secondary)', fontSize: '0.8rem' }}>
            ({signals.length}건)
          </span>
        </td>
      </tr>
      {signals.map((signal, idx) => (
        <SignalRow key={`${signal.signal_date}-${signal.ticker}-${idx}`} signal={signal} />
      ))}
    </>
  )
}

export function Signals() {
  const { data, loading, error } = useDashboardData()
  const [directionFilter, setDirectionFilter] = useState<string>('ALL')
  const [tickerFilter, setTickerFilter] = useState('')
  const [groupByTicker, setGroupByTicker] = useState(false)

  useEffect(() => {
    document.title = '시그널 검증 · Stock Research'
  }, [])

  const recentSignals = useMemo(() => data?.signal_stats?.recent_signals ?? [], [data?.signal_stats?.recent_signals])

  const tickerStats = useMemo(() => computeTickerStats(recentSignals), [recentSignals])

  const normalizedTickerFilter = tickerFilter.trim().toUpperCase()

  const filteredSignals = useMemo(
    () =>
      recentSignals.filter((s) => {
        const matchDirection = directionFilter === 'ALL' || s.signal_direction === directionFilter
        const matchTicker = normalizedTickerFilter.length === 0 || s.ticker.includes(normalizedTickerFilter)
        return matchDirection && matchTicker
      }),
    [recentSignals, directionFilter, normalizedTickerFilter],
  )

  const groupedSignals = useMemo(() => {
    if (!groupByTicker) return null
    const map = new Map<string, SignalHistoryRow[]>()
    for (const s of filteredSignals) {
      if (!map.has(s.ticker)) map.set(s.ticker, [])
      map.get(s.ticker)!.push(s)
    }
    return map
  }, [groupByTicker, filteredSignals])

  if (loading) return <TablePageSkeleton title="시그널 검증 통계" />
  if (error) return <ErrorState message={error} />
  if (!data) return <p className="status">No data available.</p>

  const signalStats = data.signal_stats
  if (!signalStats || recentSignals.length === 0) {
    return (
      <div className="signals-page">
        <h2>시그널 검증 통계</h2>
        <p className="status">시그널 데이터가 아직 축적되지 않았습니다. 파이프라인이 수일간 실행되면 자동으로 채워집니다.</p>
      </div>
    )
  }

  const summaryEntries = Object.entries(signalStats.summary_by_direction ?? {})

  // Compute overall stats
  const evaluated5d = recentSignals.filter((s) => s.evaluated_5d === 'True')
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

      {/* Ticker Summary Cards */}
      {tickerStats.length > 0 && (
        <section className="signals-meta-section">
          <div className="section-header-with-kicker">
            <div>
              <h3>종목별 성과</h3>
              <p className="section-kicker">전체 시그널 기준 종목별 건수, 승률, 평균 수익률</p>
            </div>
          </div>
          <div className="signal-summary-grid">
            {tickerStats.map((stat) => (
              <TickerSummaryCard key={stat.ticker} stat={stat} />
            ))}
          </div>
        </section>
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
        <button
          className={`dashboard-filter-btn${groupByTicker ? ' active' : ''}`}
          onClick={() => setGroupByTicker((v) => !v)}
        >
          {groupByTicker ? '종목 그룹 해제' : '종목별 그룹'}
        </button>
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
            {filteredSignals.length === 0 ? (
              <tr>
                <td colSpan={8} className="status">조건에 맞는 시그널이 없습니다.</td>
              </tr>
            ) : groupByTicker && groupedSignals ? (
              Array.from(groupedSignals.entries()).map(([ticker, rows]) => (
                <GroupedSignalRows key={ticker} ticker={ticker} signals={rows} />
              ))
            ) : (
              filteredSignals.map((signal, idx) => (
                <SignalRow key={`${signal.signal_date}-${signal.ticker}-${idx}`} signal={signal} />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
