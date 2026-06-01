import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useDashboardData } from '../hooks/useDashboardData'
import { TablePageSkeleton } from '../components/Skeleton'
import { ErrorState } from '../components/ErrorState'
import { EmptyState } from '../components/ui/EmptyState'
import type { SignalHistoryRow, SignalDirectionSummary } from '../types'

const DIRECTION_LABELS: Record<string, string> = {
  bull: '강세',
  bear: '약세',
  neutral: '중립',
}

const DIRECTION_TONE_CLASSES: Record<string, string> = {
  bull: 'signal-tone-up',
  bear: 'signal-tone-down',
  neutral: 'signal-tone-neutral',
}

function returnToneClass(value: number): string {
  if (value > 0) return 'signal-tone-up'
  if (value < 0) return 'signal-tone-down'
  return 'signal-tone-neutral'
}

function formatReturn(value: string): { text: string; toneClass: string } {
  if (!value || value === 'N/A' || value === '') return { text: '-', toneClass: 'signal-tone-muted' }
  const num = parseFloat(value)
  if (isNaN(num)) return { text: value, toneClass: 'signal-tone-muted' }
  const text = `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`
  return { text, toneClass: returnToneClass(num) }
}

function SummaryCard({ direction, summary }: { direction: string; summary: SignalDirectionSummary }) {
  const winRate = summary.win_rate_5d && summary.win_rate_5d !== 'N/A' ? summary.win_rate_5d : '-'
  const avgReturn = formatReturn(summary.avg_return_5d)

  return (
    <div className="signal-summary-card">
      <div className={`signal-summary-direction ${DIRECTION_TONE_CLASSES[direction] ?? 'signal-tone-default'}`}>
        {DIRECTION_LABELS[direction] ?? direction}
      </div>
      <div className="signal-summary-count">{summary.count}건</div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">평가 완료</span>
        <span>{summary.evaluated_5d}건</span>
      </div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">5일 승률</span>
        <span className="u-font-bold">{winRate}</span>
      </div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">5일 평균</span>
        <span className={`signal-return-value ${avgReturn.toneClass}`}>{avgReturn.text}</span>
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
  const avgRet = stat.avgReturn !== null ? formatReturn(stat.avgReturn.toFixed(2)) : { text: '-', toneClass: 'signal-tone-muted' }

  return (
    <div className="signal-summary-card">
      <div className="signal-summary-direction">
        <Link to={`/ticker/${stat.ticker}`} className="signal-summary-link">
          {stat.ticker}
        </Link>
      </div>
      <div className="signal-summary-count">{stat.count}건</div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">강세 / 약세</span>
        <span className="signal-tone-up">{stat.bullCount}</span>
        <span className="u-inline-separator">/</span>
        <span className="signal-tone-down">{stat.bearCount}</span>
      </div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">5일 승률</span>
        <span className="u-font-bold">{winRate}</span>
      </div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">5일 평균</span>
        <span className={`signal-return-value ${avgRet.toneClass}`}>{avgRet.text}</span>
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
          className={`signal-direction-chip ${DIRECTION_TONE_CLASSES[signal.signal_direction] ?? ''}`}
        >
          {DIRECTION_LABELS[signal.signal_direction] ?? signal.signal_direction}
        </span>
      </td>
      <td className="signal-numeric-cell">${signal.signal_price}</td>
      <td className="catalyst-cell">{signal.catalyst_tag || '-'}</td>
      <td className={`signal-numeric-cell ${r1d.toneClass}`}>{r1d.text}</td>
      <td className={`signal-numeric-cell ${r5d.toneClass}`}>{r5d.text}</td>
      <td className={`signal-numeric-cell ${r20d.toneClass}`}>{r20d.text}</td>
    </tr>
  )
}

function GroupedSignalRows({ ticker, signals }: { ticker: string; signals: SignalHistoryRow[] }) {
  return (
    <>
      <tr className="ticker-group-header-row">
        <td colSpan={8}>
          <Link to={`/ticker/${ticker}`} className="ticker-link u-text-sm u-font-bold">
            {ticker}
          </Link>
          <span className="u-muted-meta">
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
  if (!data) {
    return (
      <EmptyState
        title="표시할 시그널 데이터가 없습니다."
        description="파이프라인 출력이 준비되면 시그널 검증 통계가 여기에 표시됩니다."
      />
    )
  }

  const signalStats = data.signal_stats
  if (!signalStats || recentSignals.length === 0) {
    return (
      <div className="signals-page">
        <h2>시그널 검증 통계</h2>
        <EmptyState
          title="시그널 데이터가 아직 축적되지 않았습니다."
          description="파이프라인이 수일간 실행되면 검증 통계가 자동으로 채워집니다."
        />
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
      <div className="dashboard-controls u-mt-6">
        <input
          className="dashboard-search"
          type="search"
          placeholder="티커 검색"
          aria-label="시그널 티커 검색"
          value={tickerFilter}
          onChange={(e) => setTickerFilter(e.target.value)}
        />
        <select
          className="dashboard-filter"
          value={directionFilter}
          aria-label="시그널 방향 필터"
          onChange={(e) => setDirectionFilter(e.target.value)}
        >
          <option value="ALL">전체 방향</option>
          <option value="bull">강세</option>
          <option value="bear">약세</option>
          <option value="neutral">중립</option>
        </select>
        <button
          type="button"
          className={`dashboard-filter-btn${groupByTicker ? ' active' : ''}`}
          aria-pressed={groupByTicker}
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
              <th className="signal-numeric-cell">시그널가</th>
              <th>촉매</th>
              <th className="signal-numeric-cell">1D</th>
              <th className="signal-numeric-cell">5D</th>
              <th className="signal-numeric-cell">20D</th>
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
