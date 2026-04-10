import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
  ReferenceLine,
  Legend,
} from 'recharts'
import type { QuarterlyFinancialRow } from '../types'

interface Props {
  quarters: QuarterlyFinancialRow[]
}

interface ChartRow {
  quarter: string
  actualEps: number
  estimatedEps: number | null
  beatMiss: 'beat' | 'miss' | 'in-line' | 'N/A'
  surprisePct: string
}

function parseEps(v?: string): number | null {
  if (!v || v === 'N/A') return null
  const cleaned = v.replace(/[^0-9.\-+]/g, '')
  const n = parseFloat(cleaned)
  return isNaN(n) ? null : n
}

function beatMissColor(bm: string): string {
  if (bm === 'beat') return '#26a69a'
  if (bm === 'miss') return '#ef5350'
  return '#888'
}

export function EpsSurpriseChart({ quarters }: Props) {
  if (quarters.length === 0) return null

  const chartData: ChartRow[] = quarters
    .slice()
    .reverse() // oldest first for chart
    .map((q) => ({
      quarter: q.quarter,
      actualEps: parseEps(q.eps) ?? 0,
      estimatedEps: parseEps(q.estimated_eps),
      beatMiss: q.beat_miss ?? 'N/A',
      surprisePct: q.surprise_pct ?? '',
    }))
    .filter((r) => r.actualEps !== 0 || r.estimatedEps !== null)

  if (chartData.length === 0) return null

  return (
    <div className="eps-surprise-wrapper">
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 0 }} barGap={2}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
          <XAxis dataKey="quarter" tick={{ fontSize: 11 }} tickLine={false} />
          <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value: number, name: string) => {
              const label = name === 'estimatedEps' ? 'EPS 추정' : 'EPS 실제'
              return [`$${value.toFixed(2)}`, label]
            }}
          />
          <Legend
            formatter={(value: string) => (value === 'estimatedEps' ? 'EPS 추정' : 'EPS 실제')}
            wrapperStyle={{ fontSize: 11 }}
          />
          <ReferenceLine y={0} stroke="var(--color-neutral)" strokeDasharray="2 2" />
          <Bar dataKey="estimatedEps" fill="#888" opacity={0.4} radius={[2, 2, 0, 0]} barSize={18} />
          <Bar dataKey="actualEps" radius={[2, 2, 0, 0]} barSize={18}>
            {chartData.map((entry) => (
              <Cell key={entry.quarter} fill={beatMissColor(entry.beatMiss)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="eps-surprise-legend">
        {chartData.map((row) => (
          <span
            key={row.quarter}
            className={`eps-chip ${row.beatMiss}`}
          >
            {row.quarter}: {row.beatMiss}
            {row.surprisePct ? ` (${row.surprisePct})` : ''}
          </span>
        ))}
      </div>
    </div>
  )
}
