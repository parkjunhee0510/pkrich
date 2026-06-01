import { memo, useMemo } from 'react'
import type { EarningsPattern, QuarterlyFinancialRow } from '../types'

interface Props {
  quarters: QuarterlyFinancialRow[]
  earningsPattern?: EarningsPattern
}

interface ChartRow {
  quarter: string
  actualEps: number
  estimatedEps: number | null
  beatMiss: 'beat' | 'miss' | 'in-line' | 'N/A'
  surprisePct: string
}

const CHART_WIDTH = 640
const CHART_HEIGHT = 240
const PADDING = { top: 18, right: 18, bottom: 42, left: 48 }

function parseEps(v?: string): number | null {
  if (!v || v === 'N/A') return null
  const cleaned = v.replace(/[^0-9.\-+]/g, '')
  const n = Number.parseFloat(cleaned)
  return Number.isNaN(n) ? null : n
}

const BEAT_MISS_LABELS: Record<string, string> = {
  beat: '상회',
  miss: '하회',
  'in-line': '부합',
  'N/A': '미확인',
}

const SURPRISE_TREND_LABELS: Record<string, string> = {
  improving: '개선',
  deteriorating: '악화',
  stable: '안정',
  insufficient_data: '데이터 부족',
}

function beatMissColor(bm: string): string {
  if (bm === 'beat') return 'var(--pos)'
  if (bm === 'miss') return 'var(--neg)'
  return 'var(--cozy-muted)'
}

function normalizeChartRows(quarters: QuarterlyFinancialRow[]): ChartRow[] {
  return quarters
    .slice()
    .reverse()
    .map((quarter) => ({
      quarter: quarter.quarter,
      actualEps: parseEps(quarter.eps) ?? 0,
      estimatedEps: parseEps(quarter.estimated_eps),
      beatMiss: quarter.beat_miss ?? 'N/A',
      surprisePct: quarter.surprise_pct ?? '',
    }))
    .filter((row) => row.actualEps !== 0 || row.estimatedEps !== null)
}

function buildScale(rows: ChartRow[]) {
  if (rows.length === 0) {
    const yFor = () => CHART_HEIGHT / 2
    return {
      maxValue: 1,
      minValue: -1,
      yFor,
      zeroY: yFor(),
    }
  }

  const values = rows.flatMap((row) => [row.actualEps, row.estimatedEps ?? 0, 0])
  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)
  const range = maxValue - minValue || Math.max(1, Math.abs(maxValue))
  const plotHeight = CHART_HEIGHT - PADDING.top - PADDING.bottom
  const yFor = (value: number) =>
    PADDING.top + ((maxValue - value) / range) * plotHeight
  return {
    maxValue,
    minValue,
    yFor,
    zeroY: yFor(0),
  }
}

function barGeometry(value: number, zeroY: number, yFor: (value: number) => number) {
  const y = yFor(value)
  return {
    y: Math.min(y, zeroY),
    height: Math.max(1, Math.abs(zeroY - y)),
  }
}

export const EpsSurpriseChart = memo(function EpsSurpriseChart({ quarters, earningsPattern }: Props) {
  const chartData = useMemo(() => normalizeChartRows(quarters), [quarters])
  const scale = useMemo(() => buildScale(chartData), [chartData])

  if (chartData.length === 0) return null

  const plotWidth = CHART_WIDTH - PADDING.left - PADDING.right
  const slotWidth = plotWidth / chartData.length
  const groupWidth = Math.min(48, slotWidth * 0.64)
  const barWidth = Math.max(8, groupWidth / 2 - 3)
  const chartLabel = `EPS surprise chart with ${chartData.length} quarters`

  return (
    <div className="eps-surprise-wrapper">
      <svg className="performance-svg-chart eps-surprise-svg" viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} role="img" aria-label={chartLabel}>
        <title>EPS Surprise</title>
        <desc>{chartLabel}</desc>
        {[scale.minValue, 0, scale.maxValue].map((value, index) => (
          <g key={`${value}-${index}`}>
            <line
              className={value === 0 ? 'performance-svg-zero' : 'performance-svg-grid'}
              x1={PADDING.left}
              x2={CHART_WIDTH - PADDING.right}
              y1={scale.yFor(value)}
              y2={scale.yFor(value)}
            />
            <text className="performance-svg-axis" x={PADDING.left - 8} y={scale.yFor(value) + 4} textAnchor="end">
              {value.toFixed(2)}
            </text>
          </g>
        ))}
        {chartData.map((row, index) => {
          const centerX = PADDING.left + slotWidth * index + slotWidth / 2
          const estimated = row.estimatedEps === null
            ? null
            : barGeometry(row.estimatedEps, scale.zeroY, scale.yFor)
          const actual = barGeometry(row.actualEps, scale.zeroY, scale.yFor)
          return (
            <g key={row.quarter}>
              {estimated ? (
                <rect
                  x={centerX - barWidth - 2}
                  y={estimated.y}
                  width={barWidth}
                  height={estimated.height}
                  rx="3"
                  fill="var(--cozy-muted)"
                  opacity="0.46"
                >
                  <title>
                    {row.quarter} estimate: ${row.estimatedEps?.toFixed(2)}
                  </title>
                </rect>
              ) : null}
              <rect
                x={centerX + 2}
                y={actual.y}
                width={barWidth}
                height={actual.height}
                rx="3"
                fill={beatMissColor(row.beatMiss)}
              >
                <title>
                  {row.quarter} actual: ${row.actualEps.toFixed(2)} {BEAT_MISS_LABELS[row.beatMiss] ?? row.beatMiss}
                </title>
              </rect>
              <text className="performance-svg-axis" x={centerX} y={CHART_HEIGHT - 18} textAnchor="middle">
                {row.quarter}
              </text>
            </g>
          )
        })}
      </svg>
      <div className="eps-surprise-legend">
        {chartData.map((row) => (
          <span key={row.quarter} className={`eps-chip ${row.beatMiss}`}>
            {row.quarter}: {BEAT_MISS_LABELS[row.beatMiss] ?? row.beatMiss}
            {row.surprisePct ? ` (${row.surprisePct})` : ''}
          </span>
        ))}
      </div>
      {earningsPattern ? (
        <div className="eps-pattern-summary">
          {earningsPattern.beat_streak > 0 ? (
            <span className="eps-chip beat">연속 상회 {earningsPattern.beat_streak}분기</span>
          ) : null}
          <span className="eps-pattern-text">
            서프라이즈 추세 {SURPRISE_TREND_LABELS[earningsPattern.surprise_trend] ?? earningsPattern.surprise_trend}
          </span>
          <span className="eps-pattern-text">평균 서프라이즈 {earningsPattern.avg_surprise_pct}</span>
          <span className="eps-pattern-note">{earningsPattern.pattern_note}</span>
        </div>
      ) : null}
    </div>
  )
})
