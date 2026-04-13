import { useEffect, useState } from 'react'
import { ErrorState } from '../components/ErrorState'
import { TablePageSkeleton } from '../components/Skeleton'
import type { AnalyticsCostResponse } from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''

export function Admin() {
  const [data, setData] = useState<AnalyticsCostResponse | null>(null)
  const [loading, setLoading] = useState(() => Boolean(API_BASE))
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'Admin · Stock Research'
  }, [])

  useEffect(() => {
    if (!API_BASE) return
    fetch(`${API_BASE}/api/analytics/cost`, { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
      })
      .then((json: AnalyticsCostResponse) => setData(json))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <TablePageSkeleton title="Admin" />
  if (error) return <ErrorState message={error} />

  if (!API_BASE) {
    return <p className="status">Admin 비용 대시보드는 API 서버가 연결된 로컬 환경에서만 표시됩니다.</p>
  }

  return (
    <div className="signals-page">
      <div className="dashboard-header">
        <h2>Admin · 비용 / 품질</h2>
      </div>

      <div className="signal-summary-grid">
        <SummaryMetricCard label="누적 비용" value={`$${(data?.total_cost_usd ?? 0).toFixed(3)}`} note={`${data?.runs.length ?? 0} runs`} />
        <SummaryMetricCard label="평균 비용" value={`$${(data?.average_cost_usd ?? 0).toFixed(3)}`} note="일별 실행 기준" />
        <SummaryMetricCard label="성공 실행" value={`${data?.successful_runs ?? 0}`} note="기록된 analysis_runs 기준" />
      </div>

      <section className="signals-meta-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>최근 실행</h3>
            <p className="section-kicker">비용, 모델 사용량, fallback/validation 실패 추적</p>
          </div>
        </div>

        <div className="watchlist-table-shell">
          <table className="watchlist-table">
            <thead>
              <tr>
                <th>날짜</th>
                <th>성공</th>
                <th>비용</th>
                <th>배치 수</th>
                <th>Fallback</th>
                <th>Validation 실패</th>
                <th>모델</th>
              </tr>
            </thead>
            <tbody>
              {(data?.runs ?? []).map((run) => (
                <tr key={run.run_date}>
                  <td>{run.run_date}</td>
                  <td>{run.success ? 'yes' : 'no'}</td>
                  <td>${Number(run.daily_api_cost_usd ?? 0).toFixed(3)}</td>
                  <td>{run.batch_count}</td>
                  <td>{run.fallback_count}</td>
                  <td>{run.validation_failure_count}</td>
                  <td>{Object.keys(run.models_used ?? {}).length > 0 ? Object.entries(run.models_used).map(([model, count]) => `${model}×${count}`).join(', ') : 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function SummaryMetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="signal-summary-card">
      <div className="signal-summary-direction">{label}</div>
      <div className="signal-summary-count">{value}</div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">메모</span>
        <span>{note}</span>
      </div>
    </div>
  )
}
