import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import type { PriceHistoryRow } from '../types'
import { parsePrice } from '../utils/format'

interface Props {
  rows: PriceHistoryRow[]
}

export function PriceChart({ rows }: Props) {
  if (rows.length === 0) {
    return <p className="empty">Price history not available.</p>
  }

  const chartData = rows.map((r) => ({
    date: r.date,
    price: parsePrice(r.price),
  }))

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis domain={['auto', 'auto']} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="price"
            stroke="var(--color-accent)"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
