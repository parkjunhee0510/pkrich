import type { AnalysisConsensusData, TickerDecisionData } from '../types'
import { InfoTooltip } from './InfoTooltip'

const ACTION_CONFIG: Record<string, { emoji: string; label: string; className: string }> = {
  buy: { emoji: '\uD83D\uDFE2', label: '매수', className: 'decision-buy' },
  watch: { emoji: '\uD83D\uDFE1', label: '관찰', className: 'decision-watch' },
  avoid: { emoji: '\uD83D\uDD34', label: '회피', className: 'decision-avoid' },
}

const ENSEMBLE_BADGE: Record<string, { symbol: string; label: string; className: string }> = {
  agree: { symbol: '✓✓', label: '양 모델 일치', className: 'ensemble-agree' },
  conflict: { symbol: '✓✗', label: '불일치 주의', className: 'ensemble-conflict' },
  single: { symbol: '1x', label: '단일 판단', className: 'ensemble-single' },
}

const SELECTION_REASON_LABELS: Record<string, string> = {
  selected: '앙상블 대상으로 선정',
  cap_exceeded: '일일 앙상블 상한으로 보류',
  out_of_range: '앙상블 범위 밖',
  disabled: '앙상블 비활성화',
}

const FACTOR_LABELS: Record<string, string> = {
  valuation: '밸류',
  momentum: '모멘텀',
  catalyst_recency: '촉매',
  signal_track_record: '시그널',
  news_tone: '뉴스 톤',
  regime_adjustment: '매크로',
  earnings_pattern: '실적',
  fundamentals: '펀더멘털',
  macro_event: '거시 충격',
  portfolio_risk: '포트폴리오',
  peer_rank: '피어 랭크',
}

const FACTOR_CATEGORY_LABELS: Record<string, string> = {
  valuation: '밸류',
  momentum: '모멘텀',
  catalyst_recency: '촉매',
  signal_track_record: '시그널',
  news_tone: '뉴스',
  regime_adjustment: '매크로',
  earnings_pattern: '실적',
  fundamentals: '펀더멘털',
  macro_event: '거시',
  portfolio_risk: '포트폴리오',
  peer_rank: '피어 비교',
}

interface DecisionCardProps {
  decision: TickerDecisionData
  analysisConsensus?: AnalysisConsensusData
}

export function DecisionCard({ decision, analysisConsensus }: DecisionCardProps) {
  const config = ACTION_CONFIG[decision.action] ?? ACTION_CONFIG.watch
  const factorEntries = Object.entries(decision.factors ?? {})
    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
  const categoryTotals = factorEntries.reduce<Record<string, number>>((acc, [key, value]) => {
    const category = FACTOR_CATEGORY_LABELS[key] ?? '기타'
    acc[category] = (acc[category] ?? 0) + value
    return acc
  }, {})
  const categoryEntries = Object.entries(categoryTotals)
    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
  const ensemble = ENSEMBLE_BADGE[decision.ensemble_agreement ?? 'single'] ?? ENSEMBLE_BADGE.single
  const selectionReason = analysisConsensus?.selection_reason
    ? SELECTION_REASON_LABELS[analysisConsensus.selection_reason] ?? analysisConsensus.selection_reason
    : null

  return (
    <section className={`decision-card ${config.className}`}>
      <div className="decision-header">
        <div className="decision-header-stack">
          <span className="decision-action-badge">
            {config.emoji} {config.label}
          </span>
          <div className={`decision-ensemble-badge ${ensemble.className}`}>
            <span>{ensemble.symbol}</span>
            <span>{ensemble.label}</span>
            <InfoTooltip
              content={(
                <span className="metric-tooltip-copy">
                  {selectionReason ? (
                    <>
                      <strong>선정 사유</strong>
                      <span>{selectionReason}</span>
                    </>
                  ) : null}
                  {decision.ensemble_agreement === 'conflict' ? (
                    <>
                      <strong>1차 판단</strong>
                      <span>{analysisConsensus?.economy_action ?? 'watch'} · {analysisConsensus?.economy_reason ?? '사유 없음'}</span>
                      <strong>2차 판단</strong>
                      <span>{analysisConsensus?.deep_action ?? decision.action} · {analysisConsensus?.deep_reason ?? decision.reason}</span>
                    </>
                  ) : (
                    <>
                      <strong>합의 상태</strong>
                      <span>{ensemble.label}</span>
                    </>
                  )}
                </span>
              )}
            />
          </div>
        </div>
        <div className="decision-conviction-meter">
          <span className="decision-conviction-label">확신도</span>
          <div className="decision-conviction-bar">
            <div
              className="decision-conviction-fill"
              style={{ width: `${Math.min(100, Math.max(0, decision.conviction))}%` }}
            />
          </div>
          <span className="decision-conviction-value">{decision.conviction}</span>
        </div>
      </div>
      <p className="decision-reason">{decision.reason}</p>
      {decision.valid_until && (
        <span className="decision-valid-until">유효: {decision.valid_until}</span>
      )}
      {factorEntries.length > 0 && (
        <>
          <div className="decision-factors">
            {factorEntries.map(([key, value]) => (
              <span
                key={key}
                className={`decision-factor-chip ${value > 0 ? 'factor-positive' : value < 0 ? 'factor-negative' : 'factor-neutral'}`}
              >
                {FACTOR_LABELS[key] ?? key} {value > 0 ? '+' : ''}{value.toFixed(0)}
              </span>
            ))}
          </div>

          <div className="decision-breakdown">
            <div className="decision-breakdown-header">
              <strong>확신도 구성</strong>
              <span>{decision.conviction}점이 어디서 왔는지 항목별로 분해한 표입니다.</span>
            </div>

            <div className="decision-breakdown-categories">
              {categoryEntries.map(([category, value]) => (
                <div
                  key={category}
                  className={`decision-breakdown-category ${value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral'}`}
                >
                  <span className="decision-breakdown-category-label">{category}</span>
                  <strong className="decision-breakdown-category-value">
                    {value > 0 ? '+' : ''}{value.toFixed(0)}
                  </strong>
                </div>
              ))}
            </div>

            <div className="decision-breakdown-table" role="table" aria-label="확신도 점수 상세">
              <div className="decision-breakdown-row decision-breakdown-head" role="row">
                <span role="columnheader">요소</span>
                <span role="columnheader">구분</span>
                <span role="columnheader">점수</span>
              </div>
              {factorEntries.map(([key, value]) => (
                <div key={key} className="decision-breakdown-row" role="row">
                  <span role="cell">{FACTOR_LABELS[key] ?? key}</span>
                  <span role="cell">{FACTOR_CATEGORY_LABELS[key] ?? '기타'}</span>
                  <span
                    role="cell"
                    className={`decision-breakdown-score ${value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral'}`}
                  >
                    {value > 0 ? '+' : ''}{value.toFixed(0)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </section>
  )
}
