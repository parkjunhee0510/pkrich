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

function parseEps(v?: string): number | null {
  if (!v || v === 'N/A') return null
  const cleaned = v.replace(/[^0-9.\-+]/g, '')
  const n = parseFloat(cleaned)
  return isNaN(n) ? null : n
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
  if (bm === 'beat') return '#26a69a'
  if (bm === 'miss') return '#ef5350'
  return '#888'
}

export function EpsSurpriseChart({ quarters, earningsPattern }: Props) {
  if (quarters.length === 0) return null

  const chartData: ChartRow[] = quarters
    .slice()
    .reverse()
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
            formatter={(value, name) => {
              const numericValue = typeof value === 'number' ? value : Number(value ?? 0)
              const label = name === 'estimatedEps' ? 'EPS 추정' : 'EPS 실제'
              return [`$${numericValue.toFixed(2)}`, label]
            }}
          />
          <Legend
            formatter={(value) => (value === 'estimatedEps' ? 'EPS 추정' : 'EPS 실제')}
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
}
