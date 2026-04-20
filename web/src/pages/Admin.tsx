import { useEffect, useMemo, useState } from 'react'
import { ErrorState } from '../components/ErrorState'
import { SignalQualityPanel } from '../components/SignalQualityPanel'
import { TablePageSkeleton } from '../components/Skeleton'
import type {
  AnalysisQualityPayload,
  AnalyticsCostResponse,
  CostLogPayload,
  CostLogRun,
  DirectionAlignmentPayload,
} from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''
const STATIC_COST_LOG_URL = `${import.meta.env.BASE_URL}output/data/cost_log.json`
const STATIC_ANALYSIS_QUALITY_URL = `${import.meta.env.BASE_URL}output/data/analysis_quality.json`
const DIRECTION_ALIGNMENT_URL = `${import.meta.env.BASE_URL}output/data/direction_alignment.json`
const CALIBRATION_URL = `${import.meta.env.BASE_URL}output/data/calibration.json`
const FACTOR_AUDIT_URL = `${import.meta.env.BASE_URL}output/data/factor_audit.json`
const TUNING_REPORT_URL = `${import.meta.env.BASE_URL}output/data/tuning_report.json`
const VALIDATION_WARNINGS_URL = `${import.meta.env.BASE_URL}output/data/validation_warnings.json`

type DecileBucket = {
  decile: number
  conviction_min: number
  conviction_max: number
  n: number
  mean_return: number
  hit_rate: number
  ir: number
}

type ReliabilityBin = {
  bin: number
  predicted_min: number
  predicted_max: number
  predicted: number
  realized: number
  n: number
}

type DecileTable = {
  status: string
  total_evaluated: number
  horizon: number
  metric?: string
  deciles: DecileBucket[]
}

type DriftPoint = { date: string; brier: number; n: number }

type DriftReport = {
  status: string
  horizon: number
  window_days: number
  series: DriftPoint[]
  trend_slope: number | null
  latest_brier: number | null
  drift_alert?: boolean
}

type CalibrationHorizon = {
  horizon: number
  decile_buckets: DecileTable
  alpha_buckets?: DecileTable
  reliability: {
    status: string
    total_evaluated: number
    horizon: number
    brier_score: number | null
    bins: ReliabilityBin[]
  }
  drift?: DriftReport
}

type CalibrationPayload = {
  schema_version?: number
  error?: string
  horizons: Record<string, CalibrationHorizon>
}

type FactorPair = {
  factor_a: string
  factor_b: string
  rho: number
  n: number
  collinear: boolean
}

type FactorIRRow = {
  factor: string
  ir: number
  n: number
  mean_return_when_positive: number
  mean_return_when_negative: number
  weak: boolean
}

type WeightDecaySuggestion = {
  factor: string
  ir: number
  n: number
  current: { min: number; max: number }
  suggested: { min: number; max: number }
  reason: string
}

type FactorAuditHorizon = {
  horizon: number
  collinearity: {
    status: string
    sample_size: number
    threshold: number
    pairs: FactorPair[]
    collinear_pairs?: FactorPair[]
  }
  factor_ir: {
    status: string
    sample_size: number
    threshold: number
    factors: FactorIRRow[]
    weak_factors: string[]
  }
  weight_decays?: {
    status: string
    sample_size: number
    min_required_per_factor: number
    decay_factor?: number
    suggestions: WeightDecaySuggestion[]
  }
}

type FactorAuditPayload = {
  schema_version?: number
  error?: string
  horizons: Record<string, FactorAuditHorizon>
}

type TuningRegimeReport = {
  status: string
  sample_size: number
  best?: { multipliers: Record<string, number>; spearman: number } | null
  candidates?: Array<{ multipliers: Record<string, number>; spearman: number }>
}

type WalkForwardFold = {
  train_size: number
  test_size: number
  train_spearman: number | null
  oos_spearman: number
  multipliers: Record<string, number>
}

type WalkForwardRegimeReport = {
  status: string
  sample_size: number
  folds: WalkForwardFold[]
  oos_spearman_mean: number | null
  oos_spearman_std: number | null
  in_sample_spearman: number | null
  overfit_gap?: number | null
  selected_multipliers: Record<string, number> | null
}

type PurgedWalkForwardFold = {
  status?: string
  train_size: number
  purged: number
  test_size: number
  test_start?: string
  test_end?: string
  train_spearman?: number | null
  oos_spearman?: number
  multipliers?: Record<string, number>
}

type PurgedWalkForwardRegimeReport = {
  status: string
  sample_size: number
  folds: PurgedWalkForwardFold[]
  oos_spearman_mean: number | null
  oos_spearman_std: number | null
  in_sample_spearman_leaky?: number | null
  overfit_gap?: number | null
  avg_purged_per_fold?: number | null
  selected_multipliers: Record<string, number> | null
}

type TuningHorizon = {
  horizon: number
  regime_multipliers: {
    status: string
    horizon: number
    tunable_factors: string[]
    grid: number[]
    regimes: Record<string, TuningRegimeReport>
  }
  thresholds: {
    status: string
    horizon: number
    sample_size?: number
    sample_size_risk_off?: number
    suggested?: { buy: number; buy_risk_off: number; avoid: number }
  }
  walk_forward?: {
    status: string
    horizon: number
    n_folds_requested: number
    regimes: Record<string, WalkForwardRegimeReport>
  }
  purged_walk_forward?: {
    status: string
    horizon: number
    n_folds_requested: number
    embargo_days: number
    purge_horizon_days: number
    regimes: Record<string, PurgedWalkForwardRegimeReport>
  }
}

type TuningReportPayload = {
  schema_version?: number
  error?: string
  horizons: Record<string, TuningHorizon>
}

type ValidationDayPoint = {
  date: string
  batch_count: number
  validated_ticker_count: number
  validation_failure_count: number
  schema_violation_count: number
  fact_warning_count: number
  consistency_warning_count: number
  hallucination_warning_count: number
  dropped_unsupported_count: number
}

type ValidationWarningsPayload = {
  schema_version?: number
  window_days: number
  generated_at: string
  categories: string[]
  totals: Record<string, number>
  series: ValidationDayPoint[]
}

const PROFILE_LABELS: Record<string, string> = {
  economy: 'Economy',
  standard: 'Standard',
  deep: 'Deep',
}

const VALUE_HINT_LABELS: Record<string, string> = {
  deep_pass_unused: '딥 패스 미사용',
  conflict_review_value: '불일치 해소 가치 높음',
  efficient: '효율적',
  acceptable: '수용 가능',
  expensive: '비용 높음',
}

export function Admin() {
  const [data, setData] = useState<AnalyticsCostResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dataSource, setDataSource] = useState<'api' | 'static' | null>(null)
  const [calibration, setCalibration] = useState<CalibrationPayload | null>(null)
  const [analysisQuality, setAnalysisQuality] = useState<AnalysisQualityPayload | null>(null)
  const [directionAlignment, setDirectionAlignment] = useState<DirectionAlignmentPayload | null>(null)
  const [factorAudit, setFactorAudit] = useState<FactorAuditPayload | null>(null)
  const [tuningReport, setTuningReport] = useState<TuningReportPayload | null>(null)
  const [validationWarnings, setValidationWarnings] = useState<ValidationWarningsPayload | null>(null)

  useEffect(() => {
    document.title = 'Admin · Stock Research'
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadAnalysisQuality() {
      try {
        const response = await fetch(STATIC_ANALYSIS_QUALITY_URL, { cache: 'no-store' })
        if (!response.ok) return
        const json: AnalysisQualityPayload = await response.json()
        if (!cancelled) setAnalysisQuality(json)
      } catch {
        // Optional — silent fail.
      }
    }
    void loadAnalysisQuality()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadDirectionAlignment() {
      try {
        const response = await fetch(DIRECTION_ALIGNMENT_URL, { cache: 'no-store' })
        if (!response.ok) return
        const json: DirectionAlignmentPayload = await response.json()
        if (!cancelled) setDirectionAlignment(json)
      } catch {
        // Optional — silent fail.
      }
    }
    void loadDirectionAlignment()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)

      try {
        if (API_BASE) {
          const response = await fetch(`${API_BASE}/api/analytics/cost`, { cache: 'no-store' })
          if (!response.ok) throw new Error(`HTTP ${response.status}`)
          const json: AnalyticsCostResponse = await response.json()
          if (!cancelled) {
            setData(json)
            setDataSource('api')
          }
          return
        }

        const response = await fetch(STATIC_COST_LOG_URL, { cache: 'no-store' })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const costLog: CostLogPayload = await response.json()
        if (!cancelled) {
          setData(buildStaticAnalyticsResponse(costLog))
          setDataSource('static')
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadCalibration() {
      try {
        const response = await fetch(CALIBRATION_URL, { cache: 'no-store' })
        if (!response.ok) return
        const json: CalibrationPayload = await response.json()
        if (!cancelled) setCalibration(json)
      } catch {
        // Calibration is optional — silent fail.
      }
    }
    void loadCalibration()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadFactorAudit() {
      try {
        const response = await fetch(FACTOR_AUDIT_URL, { cache: 'no-store' })
        if (!response.ok) return
        const json: FactorAuditPayload = await response.json()
        if (!cancelled) setFactorAudit(json)
      } catch {
        // Factor audit is optional — silent fail.
      }
    }
    void loadFactorAudit()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadTuningReport() {
      try {
        const response = await fetch(TUNING_REPORT_URL, { cache: 'no-store' })
        if (!response.ok) return
        const json: TuningReportPayload = await response.json()
        if (!cancelled) setTuningReport(json)
      } catch {
        // Tuning report is optional — silent fail.
      }
    }
    void loadTuningReport()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadWarnings() {
      try {
        const response = await fetch(VALIDATION_WARNINGS_URL, { cache: 'no-store' })
        if (!response.ok) return
        const json: ValidationWarningsPayload = await response.json()
        if (!cancelled) setValidationWarnings(json)
      } catch {
        // Optional — silent fail.
      }
    }
    void loadWarnings()
    return () => {
      cancelled = true
    }
  }, [])

  const costRuns = data?.cost_log?.runs ?? []
  const executionRuns = analysisQuality?.runs ?? data?.runs ?? []
  const latestExecutionRun = executionRuns[0]
  const latestCostRun = costRuns[0]
  const chartMax = useMemo(
    () => Math.max(...costRuns.map((run) => Number(run.total_cost_usd ?? 0)), 0.01),
    [costRuns],
  )

  if (loading) return <TablePageSkeleton title="Admin" />
  if (error) return <ErrorState message={error} />
  if (!data) return <p className="status">Admin 비용 데이터가 아직 없습니다.</p>

  return (
    <div className="signals-page admin-page">
      <div className="dashboard-header">
        <h2>Admin · 비용 / 품질</h2>
      </div>

      <div className="signal-summary-grid">
        <SummaryMetricCard
          label="누적 비용"
          value={`$${(data.total_cost_usd ?? 0).toFixed(3)}`}
          note={`${data.runs.length}회 실행 기준`}
        />
        <SummaryMetricCard
          label="평균 비용"
          value={`$${(data.average_cost_usd ?? 0).toFixed(3)}`}
          note="일별 실행 평균"
        />
        <SummaryMetricCard
          label="성공 실행"
          value={`${data.successful_runs ?? 0}`}
          note={dataSource === 'api' ? 'API + analysis_runs 기준' : '정적 cost_log 기준'}
        />
        <SummaryMetricCard
          label="딥 패스 비용"
          value={`$${Number(latestCostRun?.deep_pass_value?.deep_cost_usd ?? 0).toFixed(3)}`}
          note={
            latestCostRun
              ? VALUE_HINT_LABELS[latestCostRun.deep_pass_value.worth_it_hint] ?? latestCostRun.deep_pass_value.worth_it_hint
              : '데이터 없음'
          }
        />
      </div>

      <section className="ticker-detail-section-shell">
        <div className="section-header-with-kicker">
          <div>
            <h3>비용 추이</h3>
            <p className="section-kicker">
              일별 총비용과 profile별 분해, deep pass 효율을 함께 봅니다.
            </p>
          </div>
          <span className="period-badge">
            {dataSource === 'api' ? 'API 연결' : '정적 JSON'}
          </span>
        </div>

        {costRuns.length > 0 ? (
          <div className="admin-cost-grid">
            <div className="admin-cost-chart">
              {costRuns.slice().reverse().map((run) => {
                const total = Number(run.total_cost_usd ?? 0)
                const height = `${Math.max((total / chartMax) * 100, total > 0 ? 8 : 4)}%`
                return (
                  <div key={run.run_date} className="admin-cost-bar-group" title={buildCostTooltip(run)}>
                    <div className="admin-cost-bar-stack">
                      {Object.entries(run.profiles).map(([profile, profileStats]) => (
                        <div
                          key={`${run.run_date}-${profile}`}
                          className={`admin-cost-bar-segment profile-${profile}`}
                          style={{ height: `${total > 0 ? (profileStats.cost_usd / total) * 100 : 0}%` }}
                        />
                      ))}
                      <div className="admin-cost-bar-total" style={{ height }} />
                    </div>
                    <span className="admin-cost-bar-date">{run.run_date.slice(5)}</span>
                  </div>
                )
              })}
            </div>

            <div className="admin-cost-sidecard">
              <strong>최신 deep pass 효율</strong>
              {latestCostRun ? (
                <div className="portfolio-risk-list">
                  <div className="portfolio-risk-row"><span>선정 종목 수</span><strong>{latestCostRun.routing.selected_count}</strong></div>
                  <div className="portfolio-risk-row"><span>불일치 종목 수</span><strong>{latestCostRun.routing.conflicted_count}</strong></div>
                  <div className="portfolio-risk-row"><span>Deep 비용</span><strong>${latestCostRun.deep_pass_value.deep_cost_usd.toFixed(3)}</strong></div>
                  <div className="portfolio-risk-row"><span>종목당 비용</span><strong>${latestCostRun.deep_pass_value.cost_per_selected_ticker_usd.toFixed(3)}</strong></div>
                  <div className="portfolio-risk-row"><span>총비용 비중</span><strong>{Math.round(latestCostRun.deep_pass_value.share_of_total_cost * 100)}%</strong></div>
                  <div className="portfolio-risk-row"><span>판정</span><strong>{VALUE_HINT_LABELS[latestCostRun.deep_pass_value.worth_it_hint] ?? latestCostRun.deep_pass_value.worth_it_hint}</strong></div>
                </div>
              ) : (
                <p className="empty">비용 로그가 아직 없습니다.</p>
              )}
            </div>
          </div>
        ) : (
          <p className="empty">cost_log 데이터가 아직 없습니다.</p>
        )}

        {latestCostRun ? (
          <div className="admin-profile-breakdown">
            {Object.entries(latestCostRun.profiles).map(([profile, stats]) => (
              <div key={profile} className="admin-profile-card">
                <span className="admin-profile-kicker">{PROFILE_LABELS[profile] ?? profile}</span>
                <strong>${stats.cost_usd.toFixed(3)}</strong>
                <p>{stats.tokens.toLocaleString()} tokens · {stats.calls} calls</p>
                <small>{Object.entries(stats.models).map(([model, count]) => `${model}×${count}`).join(', ') || '모델 기록 없음'}</small>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <ValidationWarningsSection payload={validationWarnings} />
      <DirectionAlignmentSection payload={directionAlignment} />
      <CalibrationSection payload={calibration} />
      <FactorAuditSection payload={factorAudit} />
      <SignalQualityPanel />
      <TuningReportSection payload={tuningReport} />

      <section className="signals-meta-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>최근 실행</h3>
            <p className="section-kicker">기존 analysis_runs 집계는 그대로 유지합니다.</p>
          </div>
        </div>

        <div className="watchlist-table-shell">
          <table className="watchlist-table">
            <thead>
              <tr>
                <th>날짜</th>
                <th>성공</th>
                <th>총비용</th>
                <th>배치 수</th>
                <th>Fallback</th>
                <th>Validation 실패</th>
                <th>모델</th>
              </tr>
            </thead>
            <tbody>
              {executionRuns.map((run) => (
                <tr key={run.run_date}>
                  <td>{run.run_date}</td>
                  <td>{run.success ? 'yes' : 'no'}</td>
                  <td>${Number(run.daily_api_cost_usd ?? 0).toFixed(3)}</td>
                  <td>{run.batch_count}</td>
                  <td>{'fallback_count' in run ? run.fallback_count : 0}</td>
                  <td>{run.validation_failure_count}</td>
                  <td>
                    {'models_used' in run && Object.keys(run.models_used ?? {}).length > 0
                      ? Object.entries(run.models_used).map(([model, count]) => `${model}×${count}`).join(', ')
                      : Number(run.daily_api_cost_usd ?? 0) === 0 && (run.validation_failure_count ?? 0) > 0
                        ? 'LLM quota/호출 실패'
                        : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {latestExecutionRun && Number(latestExecutionRun.daily_api_cost_usd ?? 0) === 0 && latestExecutionRun.validation_failure_count > 0 ? (
          <p className="section-kicker" style={{ marginTop: 8 }}>
            최신 실행은 LLM 비용이 0으로 기록됐습니다. 보통 OpenAI 쿼터 부족이나 호출 실패로 실제 모델 응답이 생성되지 않았을 때 이렇게 보입니다.
          </p>
        ) : null}
      </section>
    </div>
  )
}

function buildStaticAnalyticsResponse(costLog: CostLogPayload): AnalyticsCostResponse {
  const runs = (costLog.runs ?? []).map((run) => {
    const modelsUsed = Object.entries(run.profiles ?? {}).reduce<Record<string, number>>((acc, [, profileStats]) => {
      for (const [model, count] of Object.entries(profileStats.models ?? {})) {
        acc[model] = (acc[model] ?? 0) + count
      }
      return acc
    }, {})
    const totalTokens = Object.values(run.profiles ?? {}).reduce((sum, profile) => sum + (profile.tokens ?? 0), 0)
    return {
      run_date: run.run_date,
      success: run.success,
      daily_api_cost_usd: run.total_cost_usd,
      models_used: modelsUsed,
      llm_usage: { total_tokens: totalTokens },
      batch_count: run.routing.selected_count,
      fallback_count: 0,
      validation_failure_count: 0,
    }
  })

  const totalCostUsd = runs.reduce((sum, run) => sum + Number(run.daily_api_cost_usd ?? 0), 0)
  const successfulRuns = runs.filter((run) => run.success).length

  return {
    runs,
    total_cost_usd: totalCostUsd,
    average_cost_usd: runs.length > 0 ? totalCostUsd / runs.length : 0,
    successful_runs: successfulRuns,
    cost_log: costLog,
  }
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

function DirectionAlignmentSection({ payload }: { payload: DirectionAlignmentPayload | null }) {
  if (!payload) return null

  const summary = payload.summary
  const agreementRate =
    summary.agreement_rate === null || summary.agreement_rate === undefined
      ? 'N/A'
      : `${summary.agreement_rate.toFixed(1)}%`

  return (
    <section className="ticker-detail-section-shell">
      <div className="section-header-with-kicker">
        <div>
          <h3>Rule vs LLM 방향 비교</h3>
          <p className="section-kicker">
            signal_direction(룰 기반)과 llm_direction(텍스트 해석)의 누적 일치율입니다.
          </p>
        </div>
      </div>

      <div className="signal-summary-grid" style={{ marginTop: 12 }}>
        <SummaryMetricCard
          label="비교 가능 signal"
          value={`${summary.comparable_signals}`}
          note={`전체 ${summary.total_signals}건 중 방향 비교 가능한 row`}
        />
        <SummaryMetricCard
          label="일치"
          value={`${summary.agreement_count}`}
          note={`일치율 ${agreementRate}`}
        />
        <SummaryMetricCard
          label="충돌"
          value={`${summary.conflict_count}`}
          note={summary.latest_signal_date ? `최신 signal ${summary.latest_signal_date}` : '아직 집계 없음'}
        />
      </div>

      {payload.by_pair.length > 0 ? (
        <div className="watchlist-table-shell" style={{ marginTop: 16 }}>
          <table className="watchlist-table">
            <thead>
              <tr>
                <th>Rule</th>
                <th>LLM</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              {payload.by_pair.map((row) => (
                <tr key={`${row.rule_direction}|${row.llm_direction}`}>
                  <td>{row.rule_direction}</td>
                  <td>{row.llm_direction}</td>
                  <td>{row.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty" style={{ marginTop: 12 }}>
          아직 llm_direction 비교 데이터가 충분하지 않습니다.
        </p>
      )}

      {payload.recent_conflicts.length > 0 ? (
        <div className="watchlist-table-shell" style={{ marginTop: 16 }}>
          <table className="watchlist-table">
            <thead>
              <tr>
                <th>날짜</th>
                <th>티커</th>
                <th>Rule</th>
                <th>LLM</th>
                <th>촉매</th>
                <th>확신도</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {payload.recent_conflicts.map((row) => (
                <tr key={`${row.signal_date}-${row.ticker}-${row.signal_direction}-${row.llm_direction}`}>
                  <td>{row.signal_date}</td>
                  <td>{row.ticker}</td>
                  <td>{row.signal_direction}</td>
                  <td>{row.llm_direction}</td>
                  <td>{row.catalyst_tag || 'N/A'}</td>
                  <td>{row.conviction || 'N/A'}</td>
                  <td>{row.action || 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  )
}

function CalibrationSection({ payload }: { payload: CalibrationPayload | null }) {
  const [horizonKey, setHorizonKey] = useState<'1' | '5' | '20'>('5')
  const [metricKey, setMetricKey] = useState<'absolute' | 'alpha'>('alpha')

  if (!payload) return null
  if (payload.error) {
    return (
      <section className="ticker-detail-section-shell">
        <div className="section-header-with-kicker">
          <div>
            <h3>확신도 검증 (conviction calibration)</h3>
            <p className="section-kicker">calibration.json 로드 실패: {payload.error}</p>
          </div>
        </div>
      </section>
    )
  }

  const available = Object.keys(payload.horizons ?? {}) as Array<'1' | '5' | '20'>
  const activeKey = available.includes(horizonKey) ? horizonKey : available[0]
  if (!activeKey) return null
  const horizon = payload.horizons[activeKey]
  if (!horizon) return null

  const alphaTable = horizon.alpha_buckets
  const showAlpha = metricKey === 'alpha' && !!alphaTable && alphaTable.status === 'ok' && activeKey === '5'
  const activeTable = showAlpha ? alphaTable! : horizon.decile_buckets
  const deciles = activeTable.deciles ?? []
  const bins = horizon.reliability.bins ?? []
  const brier = horizon.reliability.brier_score
  const totalEvaluated = activeTable.total_evaluated ?? 0
  const insufficient = activeTable.status !== 'ok'

  return (
    <section className="ticker-detail-section-shell">
      <div className="section-header-with-kicker">
        <div>
          <h3>확신도 검증 (conviction calibration)</h3>
          <p className="section-kicker">
            conviction 10분위별 {showAlpha ? '초과 수익 (α = 개별 − 워치리스트 평균)' : '실현 수익'} · Brier 점수 낮을수록 보정 양호
          </p>
        </div>
        <div className="period-badge" style={{ display: 'flex', gap: 6 }}>
          {(['1', '5', '20'] as const).map((key) =>
            available.includes(key) ? (
              <button
                key={key}
                type="button"
                className={`nav-link${activeKey === key ? ' nav-active' : ''}`}
                style={{ padding: '2px 10px', fontSize: 12 }}
                onClick={() => setHorizonKey(key)}
              >
                {key}D
              </button>
            ) : null,
          )}
          {activeKey === '5' && alphaTable ? (
            <>
              <button
                type="button"
                className={`nav-link${metricKey === 'absolute' ? ' nav-active' : ''}`}
                style={{ padding: '2px 10px', fontSize: 12 }}
                onClick={() => setMetricKey('absolute')}
              >
                절대
              </button>
              <button
                type="button"
                className={`nav-link${metricKey === 'alpha' ? ' nav-active' : ''}`}
                style={{ padding: '2px 10px', fontSize: 12 }}
                onClick={() => setMetricKey('alpha')}
              >
                α
              </button>
            </>
          ) : null}
        </div>
      </div>

      {insufficient ? (
        <p className="empty">
          평가된 시그널이 부족합니다 (현재 {totalEvaluated}건). 20일 보유 후 데이터가 쌓이면 표시됩니다.
        </p>
      ) : (
        <>
          <div className="watchlist-table-shell" style={{ marginTop: 12 }}>
            <table className="watchlist-table">
              <thead>
                <tr>
                  <th>Decile</th>
                  <th>확신도 범위</th>
                  <th>N</th>
                  <th>평균 수익</th>
                  <th>적중률</th>
                  <th>IR</th>
                </tr>
              </thead>
              <tbody>
                {deciles.map((bucket) => (
                  <tr key={bucket.decile}>
                    <td>D{bucket.decile}</td>
                    <td>
                      {bucket.conviction_min.toFixed(0)} – {bucket.conviction_max.toFixed(0)}
                    </td>
                    <td>{bucket.n}</td>
                    <td>{bucket.mean_return >= 0 ? '+' : ''}{bucket.mean_return.toFixed(2)}%</td>
                    <td>{(bucket.hit_rate * 100).toFixed(0)}%</td>
                    <td>{bucket.ir.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="signal-summary-grid" style={{ marginTop: 16 }}>
            <SummaryMetricCard
              label="Brier score"
              value={brier !== null ? brier.toFixed(4) : 'N/A'}
              note="0에 가까울수록 보정 양호"
            />
            <SummaryMetricCard
              label="평가된 시그널"
              value={`${totalEvaluated}건`}
              note={`${activeKey}일 보유 기준`}
            />
            {horizon.drift && horizon.drift.status === 'ok' ? (
              <SummaryMetricCard
                label={`Brier 드리프트 (${horizon.drift.window_days}D MA)`}
                value={
                  horizon.drift.latest_brier !== null
                    ? horizon.drift.latest_brier.toFixed(4)
                    : 'N/A'
                }
                note={
                  horizon.drift.drift_alert
                    ? `상승 추세 (slope ${(horizon.drift.trend_slope ?? 0).toFixed(5)}) — 재보정 검토`
                    : `추세 slope ${(horizon.drift.trend_slope ?? 0).toFixed(5)}`
                }
              />
            ) : null}
          </div>

          {bins.length > 0 ? (
            <div className="watchlist-table-shell" style={{ marginTop: 12 }}>
              <table className="watchlist-table">
                <thead>
                  <tr>
                    <th>확신도 구간</th>
                    <th>예측 평균</th>
                    <th>실현 적중률</th>
                    <th>N</th>
                  </tr>
                </thead>
                <tbody>
                  {bins.map((bin) => (
                    <tr key={bin.bin}>
                      <td>
                        {(bin.predicted_min * 100).toFixed(0)}–{(bin.predicted_max * 100).toFixed(0)}
                      </td>
                      <td>{(bin.predicted * 100).toFixed(1)}%</td>
                      <td>{(bin.realized * 100).toFixed(1)}%</td>
                      <td>{bin.n}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      )}
    </section>
  )
}

function FactorAuditSection({ payload }: { payload: FactorAuditPayload | null }) {
  const [horizonKey, setHorizonKey] = useState<'5' | '20'>('5')

  if (!payload) return null
  if (payload.error) {
    return (
      <section className="ticker-detail-section-shell">
        <div className="section-header-with-kicker">
          <div>
            <h3>Factor 감사 (중복/누수)</h3>
            <p className="section-kicker">factor_audit.json 로드 실패: {payload.error}</p>
          </div>
        </div>
      </section>
    )
  }

  const available = Object.keys(payload.horizons ?? {}) as Array<'5' | '20'>
  const activeKey = available.includes(horizonKey) ? horizonKey : available[0]
  if (!activeKey) return null
  const horizon = payload.horizons[activeKey]
  if (!horizon) return null

  const { collinearity, factor_ir } = horizon
  const insufficient = collinearity.status !== 'ok' && factor_ir.status !== 'ok'

  return (
    <section className="ticker-detail-section-shell">
      <div className="section-header-with-kicker">
        <div>
          <h3>Factor 감사 (공선성 & IR)</h3>
          <p className="section-kicker">
            |ρ| ≥ {collinearity.threshold} = 병합 후보 · |IR| &lt; {factor_ir.threshold} = 약한 팩터 (드롭 검토)
          </p>
        </div>
        <div className="period-badge" style={{ display: 'flex', gap: 6 }}>
          {(['5', '20'] as const).map((key) =>
            available.includes(key) ? (
              <button
                key={key}
                type="button"
                className={`nav-link${activeKey === key ? ' nav-active' : ''}`}
                style={{ padding: '2px 10px', fontSize: 12 }}
                onClick={() => setHorizonKey(key)}
              >
                {key}D
              </button>
            ) : null,
          )}
        </div>
      </div>

      {insufficient ? (
        <p className="empty">
          평가된 시그널이 부족합니다. 10건 이상 축적되면 팩터 진단이 표시됩니다.
        </p>
      ) : (
        <>
          <h4 style={{ marginTop: 12 }}>팩터별 정보비 (Spearman ρ vs 실현 {activeKey}D 수익)</h4>
          {factor_ir.status === 'ok' && factor_ir.factors.length > 0 ? (
            <div className="watchlist-table-shell">
              <table className="watchlist-table">
                <thead>
                  <tr>
                    <th>Factor</th>
                    <th>IR</th>
                    <th>N</th>
                    <th>양수 시 평균</th>
                    <th>음수 시 평균</th>
                    <th>상태</th>
                  </tr>
                </thead>
                <tbody>
                  {factor_ir.factors.map((row) => (
                    <tr key={row.factor}>
                      <td>{row.factor}</td>
                      <td>
                        {row.ir >= 0 ? '+' : ''}
                        {row.ir.toFixed(3)}
                      </td>
                      <td>{row.n}</td>
                      <td>
                        {row.mean_return_when_positive >= 0 ? '+' : ''}
                        {row.mean_return_when_positive.toFixed(2)}%
                      </td>
                      <td>
                        {row.mean_return_when_negative >= 0 ? '+' : ''}
                        {row.mean_return_when_negative.toFixed(2)}%
                      </td>
                      <td>
                        {row.weak ? (
                          <span className="status" style={{ background: '#d98a7b' }}>
                            weak
                          </span>
                        ) : (
                          <span className="status">ok</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="empty">IR 계산에 필요한 데이터가 부족합니다 (N={factor_ir.sample_size}).</p>
          )}

          <h4 style={{ marginTop: 16 }}>팩터 쌍 공선성 (Pearson ρ)</h4>
          {collinearity.status === 'ok' && collinearity.pairs.length > 0 ? (
            <div className="watchlist-table-shell">
              <table className="watchlist-table">
                <thead>
                  <tr>
                    <th>Factor A</th>
                    <th>Factor B</th>
                    <th>ρ</th>
                    <th>N</th>
                    <th>상태</th>
                  </tr>
                </thead>
                <tbody>
                  {collinearity.pairs.slice(0, 20).map((pair) => (
                    <tr key={`${pair.factor_a}|${pair.factor_b}`}>
                      <td>{pair.factor_a}</td>
                      <td>{pair.factor_b}</td>
                      <td>
                        {pair.rho >= 0 ? '+' : ''}
                        {pair.rho.toFixed(3)}
                      </td>
                      <td>{pair.n}</td>
                      <td>
                        {pair.collinear ? (
                          <span className="status" style={{ background: '#d98a7b' }}>
                            collinear
                          </span>
                        ) : (
                          <span className="status">ok</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="empty">공선성 계산에 필요한 데이터가 부족합니다 (N={collinearity.sample_size}).</p>
          )}

          <h4 style={{ marginTop: 16 }}>Weight range 감쇠 권고 (|IR| &lt; 0.1)</h4>
          {horizon.weight_decays && horizon.weight_decays.status === 'ok' && horizon.weight_decays.suggestions.length > 0 ? (
            <div className="watchlist-table-shell">
              <table className="watchlist-table">
                <thead>
                  <tr>
                    <th>Factor</th>
                    <th>IR</th>
                    <th>N</th>
                    <th>현재 범위</th>
                    <th>권고 범위 (×{horizon.weight_decays.decay_factor ?? 0.5})</th>
                    <th>사유</th>
                  </tr>
                </thead>
                <tbody>
                  {horizon.weight_decays.suggestions.map((s) => (
                    <tr key={s.factor}>
                      <td>{s.factor}</td>
                      <td>
                        {s.ir >= 0 ? '+' : ''}
                        {s.ir.toFixed(3)}
                      </td>
                      <td>{s.n}</td>
                      <td>
                        [{s.current.min}, {s.current.max}]
                      </td>
                      <td>
                        <span className="status" style={{ background: '#d98a7b' }}>
                          [{s.suggested.min}, {s.suggested.max}]
                        </span>
                      </td>
                      <td style={{ fontSize: 12 }}>{s.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="section-kicker" style={{ marginTop: 8 }}>
                수동 적용: `config/decision_weights.yaml` 편집 후 재시작. 완전 제거는 보류.
              </p>
            </div>
          ) : (
            <p className="empty">
              감쇠 권고를 내려면 팩터당 최소{' '}
              {horizon.weight_decays?.min_required_per_factor ?? 50}
              건의 평가가 필요합니다 (현재 N={horizon.weight_decays?.sample_size ?? 0}).
            </p>
          )}
        </>
      )}
    </section>
  )
}

const VALIDATION_CATEGORY_META: Record<
  string,
  { label: string; color: string; note: string }
> = {
  schema_violation_count: {
    label: '스키마 위반',
    color: '#8b9eb7',
    note: '필드 누락/타입 불일치',
  },
  fact_warning_count: {
    label: '수치 환각',
    color: '#d98a7b',
    note: 'raw payload에 없는 가격/퍼센트 인용',
  },
  consistency_warning_count: {
    label: '톤-시그널 충돌',
    color: '#c98a2e',
    note: 'news_tone vs signal 방향 불일치',
  },
  hallucination_warning_count: {
    label: '출처 불명',
    color: '#b04a3e',
    note: '제목/URL 매칭 실패',
  },
  dropped_unsupported_count: {
    label: '필드 드롭',
    color: '#6a6a6a',
    note: 'fallback 없어 안전 기본값으로 교체',
  },
}

function ValidationWarningsSection({
  payload,
}: {
  payload: ValidationWarningsPayload | null
}) {
  if (!payload) return null

  const series = payload.series ?? []
  const categories = payload.categories ?? Object.keys(VALIDATION_CATEGORY_META)

  const maxStack = Math.max(
    1,
    ...series.map((day) =>
      categories.reduce((sum, cat) => sum + Number(day[cat as keyof ValidationDayPoint] ?? 0), 0),
    ),
  )

  const totalWarnings = categories.reduce(
    (sum, cat) => sum + Number(payload.totals[cat] ?? 0),
    0,
  )
  const totalValidated = series.reduce((sum, day) => sum + day.validated_ticker_count, 0)
  const warningRate = totalValidated > 0 ? (totalWarnings / totalValidated) * 100 : 0

  return (
    <section className="ticker-detail-section-shell">
      <div className="section-header-with-kicker">
        <div>
          <h3>LLM 환각 차단 모니터 (최근 {payload.window_days}일)</h3>
          <p className="section-kicker">
            validator가 잡아낸 카테고리별 빈도 · 총 {totalWarnings}건 / 평가 {totalValidated}건 · 발동율 {warningRate.toFixed(1)}%
          </p>
        </div>
      </div>

      <div className="signal-summary-grid" style={{ marginTop: 12 }}>
        {categories.map((cat) => {
          const meta = VALIDATION_CATEGORY_META[cat] ?? {
            label: cat,
            color: '#888',
            note: '',
          }
          return (
            <SummaryMetricCard
              key={cat}
              label={meta.label}
              value={`${payload.totals[cat] ?? 0}`}
              note={meta.note}
            />
          )
        })}
      </div>

      {series.length === 0 ? (
        <p className="empty" style={{ marginTop: 12 }}>
          아직 파이프라인 로그 요약이 없습니다.
        </p>
      ) : (
        <div className="admin-cost-grid" style={{ marginTop: 16 }}>
          <div className="admin-cost-chart">
            {series.map((day) => {
              const dayTotal = categories.reduce(
                (sum, cat) => sum + Number(day[cat as keyof ValidationDayPoint] ?? 0),
                0,
              )
              const barHeight = `${Math.max((dayTotal / maxStack) * 100, dayTotal > 0 ? 8 : 4)}%`
              const tooltip = [
                day.date,
                `총 ${dayTotal}건 / 평가 ${day.validated_ticker_count}건`,
                ...categories.map(
                  (cat) =>
                    `${VALIDATION_CATEGORY_META[cat]?.label ?? cat}: ${day[cat as keyof ValidationDayPoint] ?? 0}`,
                ),
              ].join('\n')
              return (
                <div key={day.date} className="admin-cost-bar-group" title={tooltip}>
                  <div className="admin-cost-bar-stack">
                    {categories.map((cat) => {
                      const n = Number(day[cat as keyof ValidationDayPoint] ?? 0)
                      const pct = dayTotal > 0 ? (n / dayTotal) * 100 : 0
                      const meta = VALIDATION_CATEGORY_META[cat]
                      return (
                        <div
                          key={`${day.date}-${cat}`}
                          className="admin-cost-bar-segment"
                          style={{ height: `${pct}%`, background: meta?.color ?? '#888' }}
                        />
                      )
                    })}
                    <div className="admin-cost-bar-total" style={{ height: barHeight }} />
                  </div>
                  <span className="admin-cost-bar-date">{day.date.slice(5)}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <p className="section-kicker" style={{ marginTop: 8 }}>
        발동율이 5% 초과하면 재프롬프트 루프 도입 검토 · 특정 카테고리 집중 시 프롬프트 지시 강화
      </p>
    </section>
  )
}

function TuningReportSection({ payload }: { payload: TuningReportPayload | null }) {
  const [horizonKey, setHorizonKey] = useState<'5' | '20'>('5')

  if (!payload) return null
  if (payload.error) {
    return (
      <section className="ticker-detail-section-shell">
        <div className="section-header-with-kicker">
          <div>
            <h3>가중치 튜닝 리포트 (자동 권고)</h3>
            <p className="section-kicker">tuning_report.json 로드 실패: {payload.error}</p>
          </div>
        </div>
      </section>
    )
  }

  const available = Object.keys(payload.horizons ?? {}) as Array<'5' | '20'>
  const activeKey = available.includes(horizonKey) ? horizonKey : available[0]
  if (!activeKey) return null
  const horizon = payload.horizons[activeKey]
  if (!horizon) return null

  const walkForward = horizon.walk_forward
  const thresholds = horizon.thresholds
  const regimeEntries = Object.entries(walkForward?.regimes ?? horizon.regime_multipliers.regimes)

  return (
    <section className="ticker-detail-section-shell">
      <div className="section-header-with-kicker">
        <div>
          <h3>가중치 튜닝 리포트 (자동 권고)</h3>
          <p className="section-kicker">
            walk-forward CV의 out-of-sample Spearman이 양수이고 overfit gap이 작을 때만 반영 검토 · 자동 쓰기 금지
          </p>
        </div>
        <div className="period-badge" style={{ display: 'flex', gap: 6 }}>
          {(['5', '20'] as const).map((key) =>
            available.includes(key) ? (
              <button
                key={key}
                type="button"
                className={`nav-link${activeKey === key ? ' nav-active' : ''}`}
                style={{ padding: '2px 10px', fontSize: 12 }}
                onClick={() => setHorizonKey(key)}
              >
                {key}D
              </button>
            ) : null,
          )}
        </div>
      </div>

      <h4 style={{ marginTop: 12 }}>레짐별 가중치 후보 (walk-forward)</h4>
      {regimeEntries.length === 0 ? (
        <p className="empty">평가된 시그널이 부족합니다.</p>
      ) : (
        <div className="watchlist-table-shell">
          <table className="watchlist-table">
            <thead>
              <tr>
                <th>Regime</th>
                <th>N</th>
                <th>OOS ρ (mean ± std)</th>
                <th>IS ρ</th>
                <th>Overfit gap</th>
                <th>권고 multipliers</th>
              </tr>
            </thead>
            <tbody>
              {regimeEntries.map(([regime, report]) => {
                const wf = report as WalkForwardRegimeReport
                const mults = wf.selected_multipliers
                if (wf.status !== 'ok') {
                  return (
                    <tr key={regime}>
                      <td>{regime}</td>
                      <td>{wf.sample_size}</td>
                      <td colSpan={4}>샘플 부족 ({wf.status})</td>
                    </tr>
                  )
                }
                return (
                  <tr key={regime}>
                    <td>{regime}</td>
                    <td>{wf.sample_size}</td>
                    <td>
                      {(wf.oos_spearman_mean ?? 0).toFixed(3)} ± {(wf.oos_spearman_std ?? 0).toFixed(3)}
                    </td>
                    <td>{(wf.in_sample_spearman ?? 0).toFixed(3)}</td>
                    <td>
                      {wf.overfit_gap !== null && wf.overfit_gap !== undefined ? (
                        <span
                          className="status"
                          style={{ background: wf.overfit_gap > 0.2 ? '#d98a7b' : undefined }}
                        >
                          {wf.overfit_gap >= 0 ? '+' : ''}
                          {wf.overfit_gap.toFixed(3)}
                        </span>
                      ) : (
                        'N/A'
                      )}
                    </td>
                    <td style={{ fontSize: 12 }}>
                      {mults
                        ? Object.entries(mults)
                            .map(([k, v]) => `${k}=${v}`)
                            .join(', ')
                        : 'N/A'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <PurgedWalkForwardBlock payload={horizon.purged_walk_forward} />

      <h4 style={{ marginTop: 16 }}>임계값 권고</h4>
      {thresholds.status === 'ok' && thresholds.suggested ? (
        <div className="signal-summary-grid">
          <SummaryMetricCard
            label="buy (현재 65)"
            value={`${thresholds.suggested.buy}`}
            note={`N=${thresholds.sample_size} · 70th %ile`}
          />
          <SummaryMetricCard
            label="buy_risk_off (현재 75)"
            value={`${thresholds.suggested.buy_risk_off}`}
            note={`N=${thresholds.sample_size_risk_off ?? 0} · risk_off 70th %ile`}
          />
          <SummaryMetricCard
            label="avoid (현재 35)"
            value={`${thresholds.suggested.avoid}`}
            note="30th %ile"
          />
        </div>
      ) : (
        <p className="empty">임계값 계산에 필요한 데이터가 부족합니다.</p>
      )}
    </section>
  )
}

function PurgedWalkForwardBlock({
  payload,
}: {
  payload?: TuningHorizon['purged_walk_forward']
}) {
  if (!payload) return null
  const entries = Object.entries(payload.regimes ?? {})
  if (entries.length === 0) return null

  return (
    <>
      <h4 style={{ marginTop: 16 }}>
        Purged Walk-Forward CV (embargo {payload.embargo_days}D · label horizon{' '}
        {payload.purge_horizon_days}D)
      </h4>
      <p className="section-kicker" style={{ marginBottom: 8 }}>
        학습 샘플 중 테스트 라벨 윈도우와 겹치는 행을 제거 + 양쪽에 embargo 갭을 추가 (López de Prado).
        위의 기본 walk-forward는 라벨 누수가 있을 수 있으므로, 의사결정은 이 표의 OOS ρ 기준으로.
      </p>
      <div className="watchlist-table-shell">
        <table className="watchlist-table">
          <thead>
            <tr>
              <th>Regime</th>
              <th>N</th>
              <th>OOS ρ (mean ± std)</th>
              <th>IS ρ (leaky)</th>
              <th>Overfit gap</th>
              <th>Fold당 평균 purge</th>
              <th>권고 multipliers</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([regime, report]) => {
              if (report.status !== 'ok') {
                return (
                  <tr key={regime}>
                    <td>{regime}</td>
                    <td>{report.sample_size}</td>
                    <td colSpan={5}>샘플 부족 ({report.status})</td>
                  </tr>
                )
              }
              const mults = report.selected_multipliers
              const gap = report.overfit_gap
              return (
                <tr key={regime}>
                  <td>{regime}</td>
                  <td>{report.sample_size}</td>
                  <td>
                    {(report.oos_spearman_mean ?? 0).toFixed(3)} ±{' '}
                    {(report.oos_spearman_std ?? 0).toFixed(3)}
                  </td>
                  <td>
                    {report.in_sample_spearman_leaky !== null &&
                    report.in_sample_spearman_leaky !== undefined
                      ? report.in_sample_spearman_leaky.toFixed(3)
                      : 'N/A'}
                  </td>
                  <td>
                    {gap !== null && gap !== undefined ? (
                      <span
                        className="status"
                        style={{ background: gap > 0.2 ? '#d98a7b' : undefined }}
                      >
                        {gap >= 0 ? '+' : ''}
                        {gap.toFixed(3)}
                      </span>
                    ) : (
                      'N/A'
                    )}
                  </td>
                  <td>{(report.avg_purged_per_fold ?? 0).toFixed(1)}</td>
                  <td style={{ fontSize: 12 }}>
                    {mults
                      ? Object.entries(mults)
                          .map(([k, v]) => `${k}=${v}`)
                          .join(', ')
                      : 'N/A'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <PurgedFoldDetails entries={entries} />
    </>
  )
}

function PurgedFoldDetails({
  entries,
}: {
  entries: Array<[string, PurgedWalkForwardRegimeReport]>
}) {
  const okEntries = entries.filter(([, r]) => r.status === 'ok' && r.folds.length > 0)
  if (okEntries.length === 0) return null
  return (
    <details style={{ marginTop: 8 }}>
      <summary className="section-kicker" style={{ cursor: 'pointer' }}>
        Fold별 상세 (train/purged/test_window/OOS ρ)
      </summary>
      <div className="watchlist-table-shell" style={{ marginTop: 8 }}>
        <table className="watchlist-table">
          <thead>
            <tr>
              <th>Regime</th>
              <th>Fold</th>
              <th>Train</th>
              <th>Purged</th>
              <th>Test</th>
              <th>Test 기간</th>
              <th>OOS ρ</th>
            </tr>
          </thead>
          <tbody>
            {okEntries.flatMap(([regime, report]) =>
              report.folds.map((fold, idx) => (
                <tr key={`${regime}-${idx}`}>
                  <td>{regime}</td>
                  <td>#{idx + 1}</td>
                  <td>{fold.train_size}</td>
                  <td>{fold.purged}</td>
                  <td>{fold.test_size}</td>
                  <td style={{ fontSize: 12 }}>
                    {fold.test_start ?? '—'} → {fold.test_end ?? '—'}
                  </td>
                  <td>
                    {fold.status === 'ok' && fold.oos_spearman !== undefined
                      ? fold.oos_spearman.toFixed(3)
                      : fold.status === 'skipped_small_train'
                        ? 'skipped'
                        : 'N/A'}
                  </td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
    </details>
  )
}

function buildCostTooltip(run: CostLogRun): string {
  const profileSummary = Object.entries(run.profiles)
    .map(([profile, stats]) => `${PROFILE_LABELS[profile] ?? profile}: $${stats.cost_usd.toFixed(3)}`)
    .join(' / ')
  return `${run.run_date}\n총비용 $${run.total_cost_usd.toFixed(3)}\n${profileSummary}\n선정 ${run.routing.selected_count}개`
}
