import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from 'recharts'
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

function formatCurrency(value: number): string {
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

export function EquityCurveChart({ days = [], points: backtestPoints, title = '포트폴리오 추이 (P&L)' }: Props) {
  const points: EquityPoint[] = backtestPoints && backtestPoints.length > 0
    ? backtestPoints.map((point) => {
        const cumulativeReturn = Number.parseFloat(String(point.cumulative_return).replace('%', '')) || 0
        return {
          date: point.date,
          value: point.equity_multiple * 10000,
          pnl: point.equity_multiple * 10000 - 10000,
          returnPct: cumulativeReturn,
        }
      })
    : days
        .filter((d) => d.portfolio_summary && d.portfolio_summary.total_market_value > 0)
        .map((d) => {
          const ps = d.portfolio_summary!
          return {
            date: d.date,
            value: ps.total_market_value,
            pnl: ps.total_unrealized_pnl ?? 0,
            returnPct: ps.total_unrealized_return_pct ?? 0,
          }
        })

  if (points.length < 2) {
    return (
      <div className="equity-curve-empty">
        <p className="empty">포트폴리오 추이를 표시하려면 최소 2일의 데이터가 필요합니다.</p>
      </div>
    )
  }

  const costBasis = points.length > 0 ? points[0].value - points[0].pnl : 0
  const isPositive = points[points.length - 1].pnl >= 0

  return (
    <div className="equity-curve-wrapper">
      <div className="equity-curve-header">
        <h3>{title}</h3>
        <div className="equity-curve-stats">
          <span className={`equity-stat ${isPositive ? 'positive' : 'negative'}`}>
            {isPositive ? '+' : ''}
            {formatCurrency(points[points.length - 1].pnl)}
          </span>
          <span className={`equity-stat-sub ${isPositive ? 'positive' : 'negative'}`}>
            ({isPositive ? '+' : ''}
            {points[points.length - 1].returnPct.toFixed(2)}%)
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={points} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
          <defs>
            <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={isPositive ? '#26a69a' : '#ef5350'} stopOpacity={0.3} />
              <stop offset="95%" stopColor={isPositive ? '#26a69a' : '#ef5350'} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickLine={false} />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fontSize: 11 }}
            tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value, name) => {
              const numericValue = typeof value === 'number' ? value : Number(value ?? 0)
              if (name === 'value') return [formatCurrency(numericValue), '평가금액']
              return [numericValue, String(name)]
            }}
            labelFormatter={(label) => `날짜: ${String(label ?? '')}`}
          />
          {costBasis > 0 && (
            <ReferenceLine
              y={costBasis}
              stroke="var(--color-neutral)"
              strokeDasharray="4 4"
              label={{ value: '원금', position: 'right', fontSize: 10, fill: 'var(--color-neutral)' }}
            />
          )}
          <Area
            type="monotone"
            dataKey="value"
            stroke={isPositive ? '#26a69a' : '#ef5350'}
            strokeWidth={2}
            fill="url(#equityGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
