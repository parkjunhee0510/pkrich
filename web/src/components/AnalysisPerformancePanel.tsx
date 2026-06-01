import type React from 'react'
import type {
  AnalysisPerformanceActionChange,
  AnalysisPerformanceFactorStats,
  AnalysisPerformancePayload,
  AnalysisPerformanceWindowStats,
} from '../types'

const ACTIONS = ['buy', 'watch', 'avoid'] as const
const PREFERRED_HORIZON = '5d'

type FactorRow = AnalysisPerformanceFactorStats & { factor: string }

type RegimeRow = {
  regime: string
  action: string
  stats: AnalysisPerformanceWindowStats
}

export function AnalysisPerformancePanel({ payload }: { payload: AnalysisPerformancePayload | null }) {
  if (!payload) return null

  const horizon = pickHorizon(payload.summary.completed_return_windows)
  const actionCards = ACTIONS.map((action) => ({
    action,
    stats: payload.signal_performance[action]?.[horizon] ?? null,
  })).filter((entry) => entry.stats !== null)
  const topFactors = getTopFactors(payload).slice(0, 5)
  const bestBucket = getBestConvictionBucket(payload)
  const bestRegime = getBestRegime(payload, horizon)
  const actionChanges = (payload.action_change_reasons ?? []).slice(0, 5)

  return (
    <section className="signals-meta-section analysis-performance-panel">
      <div className="section-header-with-kicker">
        <div>
          <h3>분석 성과 추적</h3>
          <p className="section-kicker">
            {payload.as_of} · 표본 {payload.summary.sample_count}건 · 결정 {payload.summary.decision_count}건
          </p>
        </div>
        <span className="period-badge ap-mode-badge">
          {payload.summary.mode === 'shadow_observational' ? 'Shadow' : payload.summary.mode}
        </span>
      </div>

      <div className="signal-summary-grid">
        {actionCards.map(({ action, stats }) => (
          <SummaryMetricCard
            key={action}
            label={`${action.toUpperCase()}`}
            sublabel={horizon.toUpperCase()}
            valueNode={<Delta value={stats?.avg_return ?? null} />}
            note={buildStatsNote(stats)}
            tone={actionTone(action)}
          />
        ))}
        {bestBucket ? (
          <SummaryMetricCard
            label="상위 확신 구간"
            valueNode={<span className="ap-summary-text">{formatBucketLabel(bestBucket.bucket)}</span>}
            note={
              <>
                <Delta value={bestBucket.stats.avg_return_5d ?? null} contextLabel="상위 확신 구간" /> · {bestBucket.stats.sample_count}건
              </>
            }
            tone="accent"
          />
        ) : null}
        {bestRegime ? (
          <SummaryMetricCard
            label="상위 레짐"
            sublabel={bestRegime.action}
            valueNode={<span className="ap-summary-text">{bestRegime.regime}</span>}
            note={
              <>
                <Delta value={bestRegime.stats.avg_return ?? null} contextLabel="상위 레짐" /> · 완료 {bestRegime.stats.completed_count}건
              </>
            }
            tone={actionTone(bestRegime.action)}
          />
        ) : null}
      </div>

      {topFactors.length > 0 ? (
        <>
          <h4 className="ap-table-heading">상위 팩터</h4>
          <div className="watchlist-table-shell">
            <table className="watchlist-table ap-table">
              <thead>
                <tr>
                  <th>Factor</th>
                  <th className="ap-num">평균 점수</th>
                  <th className="ap-num">5D 평균</th>
                  <th className="ap-num">표본</th>
                  <th>최고 맥락</th>
                </tr>
              </thead>
              <tbody>
                {topFactors.map((row) => (
                  <tr key={row.factor}>
                    <td className="ap-factor-name">{row.factor}</td>
                    <td className="ap-num">{formatNumber(row.avg_score)}</td>
                    <td className="ap-num"><Delta value={row.avg_forward_return_5d ?? null} /></td>
                    <td className="ap-num">{row.sample_count}</td>
                    <td>{renderActionContext(row.best_action_context)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {actionChanges.length > 0 ? (
        <>
          <h4 className="ap-table-heading">최근 액션 변경</h4>
          <div className="watchlist-table-shell">
            <table className="watchlist-table ap-table">
              <thead>
                <tr>
                  <th>티커</th>
                  <th>변경</th>
                  <th className="ap-num">확신도</th>
                  <th>요약</th>
                </tr>
              </thead>
              <tbody>
                {actionChanges.map((change) => (
                  <tr key={buildActionChangeKey(change)}>
                    <td className="ap-ticker">{change.ticker}</td>
                    <td><ActionShift from={change.previous_action} to={change.current_action} /></td>
                    <td className="ap-num">
                      <ConvictionShift
                        from={change.previous_conviction}
                        to={change.current_conviction}
                      />
                    </td>
                    <td className="ap-summary-cell">{change.summary}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      <p className="section-kicker ap-footnote">
        관측용 성과 추적입니다. 공식 buy / watch / avoid 판단을 재계산하거나 대체하지 않습니다.
      </p>
    </section>
  )
}

type Tone = 'pos' | 'neg' | 'caution' | 'accent' | 'muted'

function SummaryMetricCard({
  label,
  sublabel,
  valueNode,
  note,
  tone = 'muted',
}: {
  label: string
  sublabel?: string
  valueNode: React.ReactNode
  note: React.ReactNode
  tone?: Tone
}) {
  return (
    <div className={`signal-summary-card ap-summary-card ap-tone-${tone}`}>
      <div className="ap-summary-head">
        {sublabel ? <span className="sr-only">{label} {sublabel}</span> : null}
        <span className="signal-summary-direction" aria-hidden={sublabel ? 'true' : undefined}>{label}</span>
        {sublabel ? <span className="ap-summary-sublabel" aria-hidden="true">{sublabel}</span> : null}
      </div>
      <div className="signal-summary-count ap-summary-value">{valueNode}</div>
      <div className="ap-summary-note">{note}</div>
    </div>
  )
}

function Delta({
  value,
  fallback = '데이터 축적 중',
  contextLabel,
}: {
  value: number | null | undefined
  fallback?: string
  contextLabel?: string
}) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return <span className="ap-delta ap-delta-muted">{fallback}</span>
  }
  const tone: Tone = value > 0 ? 'pos' : value < 0 ? 'neg' : 'muted'
  const sign = value > 0 ? '+' : ''
  const formattedValue = value.toFixed(2)
  if (contextLabel) {
    return (
      <span className={`ap-delta ap-delta-${tone}`} aria-label={`${sign}${formattedValue}% ${contextLabel}`}>
        <span aria-hidden="true">{sign}</span>
        <span aria-hidden="true">{formattedValue}</span>
        <span aria-hidden="true">%</span>
        <span className="sr-only"> {contextLabel}</span>
      </span>
    )
  }
  return (
    <span className={`ap-delta ap-delta-${tone}`}>
      {sign}{formattedValue}%
    </span>
  )
}

const ACTION_RANK: Record<string, number> = { buy: 3, watch: 2, avoid: 1 }

function ActionShift({ from, to }: { from: string; to: string }) {
  const diff = (ACTION_RANK[to] ?? 0) - (ACTION_RANK[from] ?? 0)
  const tone: Tone = diff > 0 ? 'pos' : diff < 0 ? 'neg' : 'muted'
  const arrow = diff > 0 ? '↑' : diff < 0 ? '↓' : '→'
  return (
    <span className={`ap-shift ap-shift-${tone}`}>
      <span className="ap-shift-from">{from}</span>
      <span className="ap-shift-arrow" aria-hidden="true">{arrow}</span>
      <span className="ap-shift-to">{to}</span>
    </span>
  )
}

function ConvictionShift({ from, to }: { from: number | null | undefined; to: number | null | undefined }) {
  const fromText = formatConviction(from)
  const toText = formatConviction(to)
  const delta = (typeof to === 'number' ? to : NaN) - (typeof from === 'number' ? from : NaN)
  const tone: Tone = Number.isFinite(delta)
    ? delta > 0 ? 'pos' : delta < 0 ? 'neg' : 'muted'
    : 'muted'
  return (
    <span className={`ap-conviction-shift ap-shift-${tone}`}>
      <span className="ap-shift-from">{fromText}</span>
      <span className="ap-shift-arrow" aria-hidden="true">→</span>
      <span className="ap-shift-to">{toText}</span>
    </span>
  )
}

function actionTone(action: string): Tone {
  if (action === 'buy') return 'pos'
  if (action === 'watch') return 'caution'
  if (action === 'avoid') return 'neg'
  return 'muted'
}

function renderActionContext(context: AnalysisPerformanceFactorStats['best_action_context']) {
  if (!context) return <span className="ap-muted-cell">N/A</span>
  return (
    <span className="ap-context-cell">
      <span className={`ap-context-action ap-tone-${actionTone(context.action)}`}>{context.action}</span>
      <Delta value={context.avg_return_5d ?? null} contextLabel={`${context.action} 맥락`} />
      <span className="ap-context-n">{context.sample_count}건</span>
    </span>
  )
}

function pickHorizon(windows: string[]): string {
  if (windows.includes(PREFERRED_HORIZON)) return PREFERRED_HORIZON
  return windows[0] ?? PREFERRED_HORIZON
}

function buildStatsNote(stats: AnalysisPerformanceWindowStats | null | undefined): string {
  if (!stats) return '데이터 축적 중'
  if (stats.win_rate === null || stats.win_rate === undefined) {
    return `표본 ${stats.sample_count}건 · 완료 ${stats.completed_count}건`
  }
  return `히트율 ${formatRatio(stats.win_rate)} · 완료 ${stats.completed_count}/${stats.sample_count}`
}

function getTopFactors(payload: AnalysisPerformancePayload): FactorRow[] {
  return Object.entries(payload.factor_attribution?.factors ?? {})
    .map(([factor, stats]) => ({ factor, ...stats }))
    .filter((row) => row.avg_forward_return_5d !== null && row.sample_count > 0)
    .sort((left, right) => {
      const byReturn = (right.avg_forward_return_5d ?? Number.NEGATIVE_INFINITY) - (left.avg_forward_return_5d ?? Number.NEGATIVE_INFINITY)
      if (byReturn !== 0) return byReturn
      return right.sample_count - left.sample_count
    })
}

function getBestConvictionBucket(payload: AnalysisPerformancePayload) {
  const buckets = payload.conviction_calibration?.buckets ?? {}
  const rankedBuckets = Object.entries(buckets)
    .filter(([, stats]) => stats.avg_return_5d !== null && stats.sample_count > 0)
    .sort(([, left], [, right]) => {
      const byReturn = (right.avg_return_5d ?? Number.NEGATIVE_INFINITY) - (left.avg_return_5d ?? Number.NEGATIVE_INFINITY)
      if (byReturn !== 0) return byReturn
      return right.sample_count - left.sample_count
    })
  const best = rankedBuckets[0]
  if (!best) return null
  return { bucket: best[0], stats: best[1] }
}

function getBestRegime(payload: AnalysisPerformancePayload, horizon: string): RegimeRow | null {
  const rows: RegimeRow[] = []
  for (const [regime, byAction] of Object.entries(payload.regime_performance ?? {})) {
    for (const [action, byHorizon] of Object.entries(byAction)) {
      const stats = byHorizon[horizon]
      if (stats && stats.avg_return !== null && stats.completed_count > 0) {
        rows.push({ regime, action, stats })
      }
    }
  }
  return rows.sort((left, right) => {
    const byReturn = (right.stats.avg_return ?? Number.NEGATIVE_INFINITY) - (left.stats.avg_return ?? Number.NEGATIVE_INFINITY)
    if (byReturn !== 0) return byReturn
    return right.stats.completed_count - left.stats.completed_count
  })[0] ?? null
}

function formatBucketLabel(bucket: string): string {
  return bucket.replace('_', '-')
}

function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '데이터 축적 중'
  return `${(value * 100).toFixed(1)}%`
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return value.toFixed(2)
}

function formatConviction(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return value.toFixed(0)
}

function buildActionChangeKey(change: AnalysisPerformanceActionChange): string {
  return `${change.ticker}-${change.previous_action}-${change.current_action}-${change.current_conviction ?? 'na'}`
}
