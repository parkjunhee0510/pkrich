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
  single: { symbol: '•', label: '단일 판단', className: 'ensemble-single' },
}

const SELECTION_REASON_LABELS: Record<string, string> = {
  selected: '앙상블 대상에 선정됨',
  cap_exceeded: '일일 앙상블 상한으로 제외됨',
  out_of_range: '재분석 범위 밖이라 제외됨',
  disabled: '앙상블이 비활성화되어 단일 판단',
}

interface DecisionCardProps {
  decision: TickerDecisionData
  analysisConsensus?: AnalysisConsensusData
}

export function DecisionCard({ decision, analysisConsensus }: DecisionCardProps) {
  const config = ACTION_CONFIG[decision.action] ?? ACTION_CONFIG.watch
  const factorEntries = Object.entries(decision.factors ?? {})
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
              content={
                <span className="metric-tooltip-copy">
                  {selectionReason ? (
                    <>
                      <strong>선정 사유</strong>
                      <span>{selectionReason}</span>
                    </>
                  ) : null}
                  {decision.ensemble_agreement === 'conflict' ? (
                    <>
                      <strong>Economy</strong>
                      <span>{analysisConsensus?.economy_action ?? 'watch'} · {analysisConsensus?.economy_reason ?? '사유 없음'}</span>
                      <strong>Deep</strong>
                      <span>{analysisConsensus?.deep_action ?? decision.action} · {analysisConsensus?.deep_reason ?? decision.reason}</span>
                    </>
                  ) : (
                    <>
                      <strong>합의 상태</strong>
                      <span>{ensemble.label}</span>
                    </>
                  )}
                </span>
              }
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
      )}
    </section>
  )
}

const FACTOR_LABELS: Record<string, string> = {
  valuation: '밸류',
  momentum: '모멘텀',
  catalyst_recency: '촉매',
  signal_track_record: '신호승률',
  news_tone: '뉴스톤',
  regime_adjustment: '시장환경',
  earnings_pattern: '실적패턴',
  fundamentals: '펀더멘털',
  portfolio_risk: '포트리스크',
  peer_rank: '피어랭크',
}
