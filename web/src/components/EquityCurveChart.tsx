import { memo, useMemo } from 'react'
import type { BacktestEquityPoint, DailyEntry } from '../types'

interface Props {
  days?: DailyEntry[]
  points?: BacktestEquityPoint[]
  title?: string
}

interface EquityPoint {
  date: string
  value: number
  pnl: number
  returnPct: number
}

interface SvgPoint extends EquityPoint {
  x: number
  y: number
}

const EMPTY_DAYS: DailyEntry[] = []
const CHART_WIDTH = 640
const CHART_HEIGHT = 220
const PADDING = { top: 16, right: 20, bottom: 30, left: 54 }

function formatCurrency(value: number): string {
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

function formatAxisCurrency(value: number): string {
  if (Math.abs(value) >= 1000) {
    return `$${(value / 1000).toFixed(0)}k`
  }
  return `$${value.toFixed(0)}`
}

function normalizePoints(days: DailyEntry[], backtestPoints?: BacktestEquityPoint[]): EquityPoint[] {
  if (backtestPoints && backtestPoints.length > 0) {
    return backtestPoints.map((point) => {
      const cumulativeReturn = Number.parseFloat(String(point.cumulative_return).replace('%', '')) || 0
      return {
        date: point.date,
        value: point.equity_multiple * 10000,
        pnl: point.equity_multiple * 10000 - 10000,
        returnPct: cumulativeReturn,
      }
    })
  }

  return days
    .filter((day) => day.portfolio_summary && day.portfolio_summary.total_market_value > 0)
    .map((day) => {
      const portfolioSummary = day.portfolio_summary!
      return {
        date: day.date,
        value: portfolioSummary.total_market_value,
        pnl: portfolioSummary.total_unrealized_pnl ?? 0,
        returnPct: portfolioSummary.total_unrealized_return_pct ?? 0,
      }
    })
}

function buildSvgPoints(points: EquityPoint[]): {
  areaPath: string
  baselineY: number | null
  grid: Array<{ y: number; value: number }>
  linePoints: string
  svgPoints: SvgPoint[]
} {
  if (points.length === 0) {
    return { areaPath: '', baselineY: null, grid: [], linePoints: '', svgPoints: [] }
  }

  const values = points.map((point) => point.value)
  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)
  const range = maxValue - minValue || Math.max(1, maxValue)
  const plotWidth = CHART_WIDTH - PADDING.left - PADDING.right
  const plotHeight = CHART_HEIGHT - PADDING.top - PADDING.bottom
  const xStep = points.length > 1 ? plotWidth / (points.length - 1) : plotWidth

  const yFor = (value: number) =>
    PADDING.top + ((maxValue - value) / range) * plotHeight

  const svgPoints = points.map((point, index) => ({
    ...point, 
    x: PADDING.left + index * xStep,
    y: yFor(point.value),
  }))
  const linePoints = svgPoints.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' ')
  const bottomY = CHART_HEIGHT - PADDING.bottom
  const areaPath = svgPoints.length > 0
    ? [
        `M ${svgPoints[0].x.toFixed(1)} ${bottomY}`,
        ...svgPoints.map((point) => `L ${point.x.toFixed(1)} ${point.y.toFixed(1)}`),
        `L ${svgPoints[svgPoints.length - 1].x.toFixed(1)} ${bottomY}`,
        'Z',
      ].join(' ')
    : ''
  const grid = [0, 0.5, 1].map((ratio) => {
    const value = maxValue - range * ratio
    return { value, y: yFor(value) }
  })
  const firstValue = points[0]?.value
  const baselineY = firstValue && firstValue >= minValue && firstValue <= maxValue ? yFor(firstValue) : null

  return { areaPath, baselineY, grid, linePoints, svgPoints }
}

export const EquityCurveChart = memo(function EquityCurveChart({
  days = EMPTY_DAYS,
  points: backtestPoints,
  title = '포트폴리오 추이 (P&L)',
}: Props) {
  const points = useMemo(() => normalizePoints(days, backtestPoints), [days, backtestPoints])
  const chart = useMemo(() => buildSvgPoints(points), [points])

  if (points.length < 2) {
    return (
      <div className="equity-curve-empty">
        <p className="empty">포트폴리오 추이를 표시하려면 최소 2일의 데이터가 필요합니다.</p>
      </div>
    )
  }

  const latestPoint = points[points.length - 1]
  const isPositive = latestPoint.pnl >= 0
  const strokeColor = isPositive ? 'var(--pos)' : 'var(--neg)'
  const chartLabel = `${title}: ${points[0].date}부터 ${latestPoint.date}까지 ${formatCurrency(latestPoint.value)}`
  const markerStep = Math.max(1, Math.ceil(chart.svgPoints.length / 12))

  return (
    <div className="equity-curve-wrapper">
      <div className="equity-curve-header">
        <h3>{title}</h3>
        <div className="equity-curve-stats">
          <span className={`equity-stat ${isPositive ? 'positive' : 'negative'}`}>
            {isPositive ? '+' : ''}
            {formatCurrency(latestPoint.pnl)}
          </span>
          <span className={`equity-stat-sub ${isPositive ? 'positive' : 'negative'}`}>
            ({isPositive ? '+' : ''}
            {latestPoint.returnPct.toFixed(2)}%)
          </span>
        </div>
      </div>
      <svg className="performance-svg-chart" viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} role="img" aria-label={chartLabel}>
        <title>{title}</title>
        <desc>{chartLabel}</desc>
        {chart.grid.map((line) => (
          <g key={line.value}>
            <line className="performance-svg-grid" x1={PADDING.left} x2={CHART_WIDTH - PADDING.right} y1={line.y} y2={line.y} />
            <text className="performance-svg-axis" x={PADDING.left - 8} y={line.y + 4} textAnchor="end">
              {formatAxisCurrency(line.value)}
            </text>
          </g>
        ))}
        {chart.baselineY !== null ? (
          <line
            className="performance-svg-zero"
            x1={PADDING.left}
            x2={CHART_WIDTH - PADDING.right}
            y1={chart.baselineY}
            y2={chart.baselineY}
          />
        ) : null}
        <path d={chart.areaPath} fill={strokeColor} opacity="0.14" />
        <polyline className="performance-svg-line" points={chart.linePoints} fill="none" stroke={strokeColor} strokeWidth="3" />
        {chart.svgPoints.map((point, index) =>
          index === 0 || index === chart.svgPoints.length - 1 || index % markerStep === 0 ? (
            <circle key={point.date} className="performance-svg-point" cx={point.x} cy={point.y} r="3" fill={strokeColor}>
              <title>
                {point.date}: {formatCurrency(point.value)} ({point.returnPct.toFixed(2)}%)
              </title>
            </circle>
          ) : null,
        )}
        <text className="performance-svg-axis" x={PADDING.left} y={CHART_HEIGHT - 8}>
          {points[0].date}
        </text>
        <text className="performance-svg-axis" x={CHART_WIDTH - PADDING.right} y={CHART_HEIGHT - 8} textAnchor="end">
          {latestPoint.date}
        </text>
      </svg>
    </div>
  )
})
