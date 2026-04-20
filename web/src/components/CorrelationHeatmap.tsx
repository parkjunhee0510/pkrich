import { useMemo, useState } from 'react'
import type { SectorsPricePoint, SectorsTicker } from '../hooks/useSectorsData'

type Window = '30d' | '60d' | '90d'

const WINDOW_DAYS: Record<Window, number> = {
  '30d': 30,
  '60d': 60,
  '90d': 90,
}

interface Props {
  tickers: SectorsTicker[]
}

interface MatrixEntry {
  ticker: string
  returns: number[]
}

/**
 * Pairwise Pearson correlation of daily returns for a sector's tickers.
 * Uses data already shipped in sectors.json -- no extra API calls.
 *
 * Skips tickers whose data was reused from the watchlist (no history) and
 * any series shorter than the selected lookback. When fewer than 2 tickers
 * remain, the heatmap is suppressed.
 */
export function CorrelationHeatmap({ tickers }: Props) {
  const [window, setWindow] = useState<Window>('30d')
  const [hover, setHover] = useState<{ row: number; col: number } | null>(null)

  const entries = useMemo(
    () => buildReturnSeries(tickers, WINDOW_DAYS[window]),
    [tickers, window],
  )
  const matrix = useMemo(() => buildMatrix(entries), [entries])

  if (entries.length < 2) return null

  return (
    <section className="corr-heatmap">
      <header className="corr-heatmap-head">
        <h2>섹터 내 상관계수</h2>
        <div className="corr-heatmap-toggle">
          {(['30d', '60d', '90d'] as const).map((w) => (
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

      <div className="corr-heatmap-grid-wrap">
        <table className="corr-heatmap-grid">
          <thead>
            <tr>
              <th />
              {entries.map((e) => (
                <th key={e.ticker} className="corr-col-label">
                  <span>{e.ticker}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {entries.map((rowEntry, r) => (
              <tr key={rowEntry.ticker}>
                <th className="corr-row-label">{rowEntry.ticker}</th>
                {entries.map((colEntry, c) => {
                  const v = matrix[r][c]
                  const isDiag = r === c
                  const active = hover && hover.row === r && hover.col === c
                  return (
                    <td
                      key={colEntry.ticker}
                      className={`corr-cell ${active ? 'active' : ''}`}
                      style={{ background: isDiag ? 'transparent' : colorFor(v) }}
                      title={
                        isDiag
                          ? ''
                          : `${rowEntry.ticker} · ${colEntry.ticker}: ${v.toFixed(2)}`
                      }
                      onMouseEnter={() => setHover({ row: r, col: c })}
                      onMouseLeave={() => setHover(null)}
                    >
                      {isDiag ? '' : v.toFixed(2)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="corr-heatmap-footnote">
        일간 수익률의 Pearson 상관. 파란색은 음의 상관(분산 효과), 빨간색은 양의 상관(함께
        움직임). 대각선은 생략. 워치리스트 중복 티커 · 히스토리 부족 티커는 제외됩니다.
      </p>
    </section>
  )
}

function buildReturnSeries(tickers: SectorsTicker[], lookback: number): MatrixEntry[] {
  const out: MatrixEntry[] = []
  for (const t of tickers) {
    if (t.error === 'reuse_from_watchlist') continue
    const returns = dailyReturns(t.history, lookback)
    if (returns.length < Math.min(lookback, 20)) continue  // need enough data
    out.push({ ticker: t.ticker, returns })
  }
  return out
}

function dailyReturns(history: SectorsPricePoint[], lookback: number): number[] {
  if (history.length < 2) return []
  // Slice the last `lookback + 1` closes so we compute `lookback` returns.
  const sliceLen = lookback + 1
  const slice = history.length > sliceLen ? history.slice(-sliceLen) : history
  const out: number[] = []
  for (let i = 1; i < slice.length; i += 1) {
    const prev = slice[i - 1].close
    const curr = slice[i].close
    if (!prev || !Number.isFinite(curr)) continue
    out.push((curr - prev) / prev)
  }
  return out
}

function buildMatrix(entries: MatrixEntry[]): number[][] {
  const n = entries.length
  const matrix: number[][] = Array.from({ length: n }, () => Array(n).fill(0))
  for (let i = 0; i < n; i += 1) {
    for (let j = i; j < n; j += 1) {
      const c = i === j ? 1 : pearson(entries[i].returns, entries[j].returns)
      matrix[i][j] = c
      matrix[j][i] = c
    }
  }
  return matrix
}

function pearson(a: number[], b: number[]): number {
  // Align to the shorter tail -- series can differ slightly if one ticker
  // has fewer history points (recent IPO, trading halt).
  const n = Math.min(a.length, b.length)
  if (n < 3) return 0
  const aTail = a.slice(-n)
  const bTail = b.slice(-n)
  const meanA = aTail.reduce((s, v) => s + v, 0) / n
  const meanB = bTail.reduce((s, v) => s + v, 0) / n
  let cov = 0
  let varA = 0
  let varB = 0
  for (let i = 0; i < n; i += 1) {
    const da = aTail[i] - meanA
    const db = bTail[i] - meanB
    cov += da * db
    varA += da * da
    varB += db * db
  }
  const denom = Math.sqrt(varA * varB)
  if (denom === 0) return 0
  return cov / denom
}

function colorFor(v: number): string {
  // Clamp [-1, 1] and interpolate through white.
  const clamped = Math.max(-1, Math.min(1, v))
  if (clamped >= 0) {
    // white → red
    const alpha = clamped * 0.75
    return `rgba(239, 83, 80, ${alpha.toFixed(3)})`
  }
  const alpha = Math.abs(clamped) * 0.55
  return `rgba(79, 128, 210, ${alpha.toFixed(3)})`
}
