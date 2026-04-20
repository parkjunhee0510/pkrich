import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { SectorsSector, SectorsTicker } from '../hooks/useSectorsData'

type Window = '1m' | '3m' | '6m'

interface SectorStat {
  id: string
  name: string
  avgReturn: number       // mean ticker return in the window (%)
  breadth: number         // share of tickers with positive return (0-1)
  coveredTickers: number  // tickers that had enough history
  totalTickers: number
}

// ~21 trading days per month. Used as a rough lookback window over the
// daily close series we already ship in sectors.json.
const WINDOW_DAYS: Record<Window, number> = {
  '1m': 21,
  '3m': 63,
  '6m': 126,
}

export function SectorPerformanceBars({ sectors }: { sectors: SectorsSector[] }) {
  const [window, setWindow] = useState<Window>('1m')

  const stats = useMemo(() => computeSectorStats(sectors, window), [sectors, window])
  const maxAbs = useMemo(
    () => Math.max(1, ...stats.map((s) => Math.abs(s.avgReturn))),
    [stats],
  )

  if (stats.length === 0) {
    return null
  }

  return (
    <section className="sector-perf">
      <header className="sector-perf-head">
        <h2>섹터 상대 성과</h2>
        <div className="sector-perf-toggle">
          {(['1m', '3m', '6m'] as const).map((w) => (
            <button
              key={w}
              type="button"
              className={`preset-chip ${window === w ? 'active' : ''}`}
              onClick={() => setWindow(w)}
            >
              {w.toUpperCase()}
            </button>
          ))}
        </div>
      </header>
      <ul className="sector-perf-list">
        {stats.map((s) => (
          <li key={s.id}>
            <Link to={`/sectors/${s.id}`} className="sector-perf-row">
              <span className="sector-perf-name">{s.name}</span>
              <div className="sector-perf-bar-wrap">
                <SectorBar value={s.avgReturn} maxAbs={maxAbs} />
              </div>
              <span
                className={`sector-perf-value ${s.avgReturn >= 0 ? 'positive' : 'negative'}`}
              >
                {formatPercent(s.avgReturn)}
              </span>
              <span className="sector-perf-breadth" title="양의 수익률 종목 비율">
                {Math.round(s.breadth * 100)}%
                <span className="sector-perf-breadth-meta">
                  {' '}
                  ({s.coveredTickers}/{s.totalTickers})
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="sector-perf-footnote">
        섹터 내 종목 평균 수익률 기준 · 오른쪽은 상승 종목 비중(breadth) · 워치리스트 중복
        종목은 섹터 데이터에서 제외되어 합산에서 빠집니다.
      </p>
    </section>
  )
}

function SectorBar({ value, maxAbs }: { value: number; maxAbs: number }) {
  const widthPct = Math.min(100, (Math.abs(value) / maxAbs) * 100)
  const positive = value >= 0
  return (
    <div className="sector-perf-bar">
      <div className="sector-perf-bar-track">
        <div className="sector-perf-bar-center" />
        <div
          className={`sector-perf-bar-fill ${positive ? 'positive' : 'negative'}`}
          style={{
            width: `${widthPct / 2}%`,
            left: positive ? '50%' : undefined,
            right: positive ? undefined : '50%',
          }}
        />
      </div>
    </div>
  )
}

function computeSectorStats(sectors: SectorsSector[], window: Window): SectorStat[] {
  const lookback = WINDOW_DAYS[window]
  const stats = sectors.map((sector) => {
    const returns: number[] = []
    for (const ticker of sector.tickers) {
      const ret = tickerReturn(ticker, lookback)
      if (ret !== null) returns.push(ret)
    }
    const avgReturn = returns.length
      ? returns.reduce((a, b) => a + b, 0) / returns.length
      : 0
    const positives = returns.filter((r) => r > 0).length
    const breadth = returns.length ? positives / returns.length : 0
    return {
      id: sector.id,
      name: sector.name,
      avgReturn,
      breadth,
      coveredTickers: returns.length,
      totalTickers: sector.tickers.length,
    }
  })
  // Sort strongest → weakest so the leader is at the top.
  return stats.sort((a, b) => b.avgReturn - a.avgReturn)
}

function tickerReturn(ticker: SectorsTicker, lookback: number): number | null {
  if (ticker.error === 'reuse_from_watchlist') return null
  const h = ticker.history
  if (h.length < 2) return null
  const last = h[h.length - 1]?.close
  // Clamp lookback to available data so 1m still works on shorter series.
  const startIdx = Math.max(0, h.length - 1 - lookback)
  const start = h[startIdx]?.close
  if (!last || !start) return null
  return ((last - start) / start) * 100
}

function formatPercent(v: number): string {
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}%`
}
