import type { SectorsBenchmark } from '../hooks/useSectorsData'
import { windowReturn } from '../utils/sectorBenchmark'
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

function formatPercent(v: number): string {
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}%`
}
