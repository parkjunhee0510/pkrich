import type React from 'react'
import type {
  AiRecommendationBacktestPayload,
  AiRecommendationExample,
  AiRecommendationWindowStats,
} from '../types'

const ACTIONS = ['buy', 'watch', 'avoid'] as const
const ACTION_LABELS: Record<string, string> = {
  buy: 'BUY',
  watch: 'WATCH',
  avoid: 'AVOID',
}

export function AiRecommendationBacktestPanel({
  payload,
}: {
  payload?: AiRecommendationBacktestPayload | null
}) {
  if (!payload) return null

  if (payload.status !== 'ok') {
    return (
      <section className="signals-meta-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>AI 추천 백테스팅</h3>
            <p className="section-kicker">
              평가 기간이 더 쌓이면 AI 추천 백테스팅이 표시됩니다.
            </p>
          </div>
        </div>
      </section>
    )
  }

  const buy20d = getActionStats(payload, 'buy', '20d')
  const avoid20d = getActionStats(payload, 'avoid', '20d')
  const highConvictionBuy = getHighConvictionBuyStats(payload)
  const summary = payload.summary ?? { sample_count: 0, completed_20d_count: 0 }
  const bestExamples = payload.notable_examples?.best ?? []
  const worstExamples = payload.notable_examples?.worst ?? []

  return (
    <section className="signals-meta-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>AI 추천 백테스팅</h3>
          <p className="section-kicker">
            최종 buy / watch / avoid 판단이 이후 1일, 5일, 20일 수익률과 얼마나 맞았는지 추적합니다.
          </p>
        </div>
        <span className="period-badge ap-mode-badge">{payload.basis}</span>
      </div>

      <div className="signal-summary-grid">
        <SummaryMetricCard
          label="BUY 추천 승률"
          value={formatRatio(buy20d?.win_rate)}
          note={`20D 평균 ${formatPercent(buy20d?.avg_return)} · ${formatEvaluatedBasis(buy20d, 'BUY')}`}
          tone="pos"
        />
        <SummaryMetricCard
          label="고확신 BUY"
          value={formatPercent(highConvictionBuy?.stats.avg_return)}
          note={`승률 ${formatRatio(highConvictionBuy?.stats.win_rate)} · ${formatEvaluatedBasis(highConvictionBuy?.stats, '고확신 BUY')} · ${formatBucketLabel(highConvictionBuy?.bucket)}`}
          tone="accent"
        />
        <SummaryMetricCard
          label="AVOID 방어 성공률"
          value={formatActionWinRate(avoid20d, 'avoid')}
          note={
            hasNoSamples(avoid20d)
              ? '아직 최종 AVOID 추천 표본이 없습니다.'
              : `20D 평균 ${formatPercent(avoid20d?.avg_return)} · 완료 ${formatCompletedCount(avoid20d)}`
          }
          tone="neg"
        />
        <SummaryMetricCard
          label="평가 완료"
          value={`${formatInteger(summary.completed_20d_count)}건`}
          note={`전체 표본 ${formatInteger(summary.sample_count)}건`}
          tone="muted"
        />
      </div>

      <h4 className="ap-table-heading">액션별 추천 성과</h4>
      <div className="watchlist-table-shell">
        <table className="watchlist-table ap-table">
          <thead>
            <tr>
              <th>추천</th>
              <th className="ap-num">1D 평균</th>
              <th className="ap-num">5D 평균</th>
              <th className="ap-num">20D 평균</th>
              <th className="ap-num">20D 승률</th>
              <th className="ap-num">평가/전체</th>
            </tr>
          </thead>
          <tbody>
            {ACTIONS.map((action) => {
              const oneDay = getActionStats(payload, action, '1d')
              const fiveDay = getActionStats(payload, action, '5d')
              const twentyDay = getActionStats(payload, action, '20d')
              return (
                <tr key={action}>
                  <td className="ap-ticker">{ACTION_LABELS[action]}</td>
                  <td className="ap-num">{formatActionAverage(oneDay)}</td>
                  <td className="ap-num">{formatActionAverage(fiveDay)}</td>
                  <td className="ap-num">{formatActionAverage(twentyDay)}</td>
                  <td className="ap-num">{formatActionWinRate(twentyDay, action)}</td>
                  <td className="ap-num">{formatCompletedCount(twentyDay)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {renderExamplesTable('잘 맞은 추천', bestExamples)}
      {renderExamplesTable('틀린 추천', worstExamples)}

      <p className="section-kicker ap-footnote">
        이 지표는 사후 검증용이며 공식 투자 판단이나 다음 실행 로직을 변경하지 않습니다.
      </p>
    </section>
  )
}

type Tone = 'pos' | 'neg' | 'accent' | 'muted'

function SummaryMetricCard({
  label,
  value,
  note,
  tone,
}: {
  label: string
  value: React.ReactNode
  note: React.ReactNode
  tone: Tone
}) {
  return (
    <div className={`signal-summary-card ap-summary-card ap-tone-${tone}`}>
      <div className="signal-summary-direction">{label}</div>
      <div className="signal-summary-count ap-summary-value">{value}</div>
      <div className="ap-summary-note">{note}</div>
    </div>
  )
}

function renderExamplesTable(title: string, rows: AiRecommendationExample[]) {
  return (
    <>
      <h4 className="ap-table-heading">{title}</h4>
      <div className="watchlist-table-shell">
        <table className="watchlist-table ap-table">
          <thead>
            <tr>
              <th>날짜</th>
              <th>티커</th>
              <th>액션</th>
              <th className="ap-num">확신도</th>
              <th className="ap-num">20D</th>
            </tr>
          </thead>
          <tbody>
            {rows.length > 0 ? (
              rows.map((row, index) => (
                <tr key={`${row.signal_date}-${row.ticker}-${row.action}-${index}`}>
                  <td>{row.signal_date || 'N/A'}</td>
                  <td className="ap-ticker">{row.ticker || 'N/A'}</td>
                  <td>{ACTION_LABELS[row.action] ?? row.action}</td>
                  <td className="ap-num">{formatConviction(row.conviction)}</td>
                  <td className="ap-num">{formatPercent(row.return_20d)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5}>N/A</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}

function getActionStats(
  payload: AiRecommendationBacktestPayload,
  action: string,
  horizon: string,
): AiRecommendationWindowStats | null {
  return (payload.by_action ?? {})[action]?.[horizon] ?? null
}

function getHighConvictionBuyStats(
  payload: AiRecommendationBacktestPayload,
): { bucket: string; stats: AiRecommendationWindowStats } | null {
  const buckets = payload.conviction_buckets ?? {}
  for (const bucket of ['80_100', '65_80']) {
    const stats = buckets[bucket]?.by_action?.buy?.['20d']
    if (stats && stats.completed_count > 0 && stats.avg_return !== null) {
      return { bucket, stats }
    }
  }
  return null
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return `${(value * 100).toFixed(1)}%`
}

function formatActionAverage(stats: AiRecommendationWindowStats | null | undefined): string {
  if (hasNoSamples(stats)) return '표본 없음'
  if (stats && stats.completed_count === 0) return '평가 대기'
  return formatPercent(stats?.avg_return)
}

function formatActionWinRate(
  stats: AiRecommendationWindowStats | null | undefined,
  action: string,
): string {
  if (hasNoSamples(stats)) return '표본 없음'
  if (action === 'watch') return '방향 없음'
  if (stats && stats.completed_count === 0) return '평가 대기'
  return formatRatio(stats?.win_rate)
}

function formatConviction(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return value.toFixed(0)
}

function formatCompletedCount(stats: AiRecommendationWindowStats | null | undefined): string {
  if (!stats) return 'N/A'
  return `${formatInteger(stats.completed_count)}/${formatInteger(stats.sample_count)}`
}

function formatEvaluatedBasis(
  stats: AiRecommendationWindowStats | null | undefined,
  label: string,
): string {
  if (!stats) return '평가 대기'
  if (stats.sample_count === 0) return `전체 ${label} 표본 없음`
  return `평가완료 ${formatInteger(stats.completed_count)}건 기준 · 전체 ${label} ${formatInteger(stats.sample_count)}건`
}

function formatInteger(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return value.toFixed(0)
}

function formatBucketLabel(bucket: string | null | undefined): string {
  if (!bucket) return 'N/A'
  return bucket.replace('_', '-')
}

function hasNoSamples(stats: AiRecommendationWindowStats | null | undefined): boolean {
  return Boolean(stats && stats.sample_count === 0)
}
