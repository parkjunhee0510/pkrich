import type { SectorsBenchmark, SectorsPricePoint } from '../hooks/useSectorsData'
import { Sparkline } from './Sparkline'

const WINDOWS: { label: string; days: number }[] = [
  { label: '1M', days: 21 },
  { label: '3M', days: 63 },
  { label: '6M', days: 126 },
  { label: 'YTD', days: -1 },   // -1 = full series (defaults to ~1y)
]

export function SectorBenchmarkHeader({
  benchmark,
}: {
  benchmark: SectorsBenchmark
}) {
  const closes = benchmark.history.map((p) => p.close)

  if (benchmark.error || closes.length < 2) {
    return (
      <section className="sector-benchmark">
        <div className="sector-benchmark-head">
          <span className="sector-benchmark-label">벤치마크</span>
          <strong>{benchmark.ticker}</strong>
          <span className="sector-ticker-note muted">
            데이터를 불러오지 못했습니다 ({benchmark.error || 'no_history'})
          </span>
        </div>
      </section>
    )
  }

  const changeClass = benchmark.change_percent.startsWith('-') ? 'negative' : 'positive'

  return (
    <section className="sector-benchmark">
      <div className="sector-benchmark-head">
        <span className="sector-benchmark-label">벤치마크</span>
        <strong>{benchmark.ticker}</strong>
        <span className="price">{benchmark.price}</span>
        <span className={`change ${changeClass}`}>{benchmark.change_percent}</span>
      </div>
      <div className="sector-benchmark-sparkline">
        <Sparkline values={closes} width={420} height={50} />
      </div>
      <ul className="sector-benchmark-windows">
        {WINDOWS.map(({ label, days }) => {
          const ret = windowReturn(benchmark.history, days)
          if (ret === null) return null
          return (
            <li key={label}>
              <span className="window-label">{label}</span>
              <span className={`window-value ${ret >= 0 ? 'positive' : 'negative'}`}>
                {formatPercent(ret)}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/**
 * Ticker vs benchmark relative return over the given lookback.
 * Returns null when either series is too short. Used inline on each
 * sector ticker card.
 */
export function relativeReturn(
  tickerHistory: SectorsPricePoint[],
  benchmarkHistory: SectorsPricePoint[],
  lookback: number,
): { ticker: number; benchmark: number; relative: number } | null {
  const t = windowReturn(tickerHistory, lookback)
  const b = windowReturn(benchmarkHistory, lookback)
  if (t === null || b === null) return null
  return { ticker: t, benchmark: b, relative: t - b }
}

function windowReturn(history: SectorsPricePoint[], lookback: number): number | null {
  if (history.length < 2) return null
  const last = history[history.length - 1]?.close
  const startIdx = lookback < 0
    ? 0
    : Math.max(0, history.length - 1 - lookback)
  const start = history[startIdx]?.close
  if (!last || !start) return null
  return ((last - start) / start) * 100
}

function formatPercent(v: number): string {
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}%`
}
