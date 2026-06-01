import type {
  PerformanceBaselinePayload,
  PerformanceTrendRun,
  PerformanceTrendsPayload,
} from '../types'

export function PerformanceMeasurementPanel({
  baseline,
  trends,
}: {
  baseline: PerformanceBaselinePayload | null
  trends: PerformanceTrendsPayload | null
}) {
  if (!baseline) return null

  const recentRuns = (trends?.runs ?? []).slice(-6).reverse()

  return (
    <section className="ticker-detail-section-shell">
      <div className="section-header-with-kicker">
        <div>
          <h3>성능 기준선</h3>
          <p className="section-kicker">
            {baseline.as_of} · latest {baseline.latest_run_date || 'N/A'}
          </p>
        </div>
        <span className="period-badge">{baseline.status}</span>
      </div>

      <div className="signal-summary-grid">
        <SummaryMetricCard
          label="월간 비용"
          value={`${formatCurrency(baseline.cost.estimated_monthly_cost_usd, 2)} / ${formatCurrency(baseline.cost.monthly_budget_usd, 2)}`}
          note={`${formatRatio(baseline.cost.budget_usage_ratio)} 사용`}
        />
        <SummaryMetricCard
          label="LLM 호출"
          value={`${baseline.cost.llm_calls} calls`}
          note={`${formatNumber(baseline.cost.llm_calls_per_ticker, 3)} calls/ticker · deep ${baseline.cost.deep_selected_count}건`}
        />
        <SummaryMetricCard
          label="품질 경고"
          value={formatRatio(baseline.quality.hallucination_ratio)}
          note={`validation ${formatRatio(baseline.quality.validation_failure_rate)} · fact ${baseline.quality.fact_warning_count}건`}
        />
        <SummaryMetricCard
          label="증거 커버리지"
          value={formatRatio(baseline.evidence.coverage_ratio)}
          note={`covered ${baseline.evidence.covered_ticker_count}/${baseline.evidence.ticker_count} · provider ${baseline.evidence.provider || 'N/A'}`}
        />
        <SummaryMetricCard
          label="Priority evidence"
          value={formatRatio(baseline.evidence.priority_coverage_ratio)}
          note={`${baseline.evidence.priority_covered_ticker_count}/${baseline.evidence.priority_ticker_count} prioritized; ${formatCounts(baseline.evidence.priority_status_counts)}`}
        />
        <SummaryMetricCard
          label="Evidence cache"
          value={formatRatio(baseline.evidence.cache_hit_ratio)}
          note={`${formatNumber(baseline.evidence.stale_cache_hit_count, 0)}/${formatNumber(baseline.evidence.cache_hit_count, 0)} stale; avg ${formatNumber(baseline.evidence.average_cache_age_hours, 1)}h, max ${formatNumber(baseline.evidence.max_cache_age_hours, 0)}h; TTL ${formatNumber(baseline.evidence.cache_ttl_hours, 0)}h`}
        />
        <SummaryMetricCard
          label="JSON health"
          value={`${baseline.json_health.invalid_json_count} invalid`}
          note={baseline.json_health.status}
        />
        <SummaryMetricCard
          label="BudgetGuard"
          value={`${baseline.cost.budget_guard_would_block_count} would-block`}
          note={`blocked ${baseline.cost.budget_guard_blocked_count}`}
        />
      </div>

      {recentRuns.length > 0 ? (
        <>
          <h4 className="u-mt-4">최근 성능 추세</h4>
          <div className="watchlist-table-shell">
            <table className="watchlist-table">
              <thead>
                <tr>
                  <th>날짜</th>
                  <th>비용</th>
                  <th>LLM calls</th>
                  <th>Hallucination</th>
                  <th>Validation 실패</th>
                  <th>Deep</th>
                  <th>BudgetGuard</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((run) => (
                  <TrendRow key={run.run_date} run={run} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  )
}

function TrendRow({ run }: { run: PerformanceTrendRun }) {
  return (
    <tr>
      <td>{run.run_date}</td>
      <td>{formatCurrency(run.total_cost_usd, 3)}</td>
      <td>{run.llm_calls}</td>
      <td>{formatRatio(run.hallucination_ratio)}</td>
      <td>{run.validation_failure_count}</td>
      <td>{run.deep_selected_count}</td>
      <td>{run.budget_guard_would_block_count}</td>
    </tr>
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

function formatCurrency(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return `$${value.toFixed(digits)}`
}

function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return `${(value * 100).toFixed(1)}%`
}

function formatNumber(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return value.toFixed(digits)
}

function formatCounts(counts: Record<string, number> | null | undefined): string {
  const entries = Object.entries(counts ?? {}).sort(([left], [right]) => left.localeCompare(right))
  if (entries.length === 0) return 'no statuses'
  return entries.map(([key, value]) => `${key}=${value}`).join(', ')
}
