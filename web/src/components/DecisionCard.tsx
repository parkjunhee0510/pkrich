import type { TickerDecisionData } from '../types'

const ACTION_CONFIG: Record<string, { emoji: string; label: string; className: string }> = {
  buy: { emoji: '\uD83D\uDFE2', label: '\uB9E4\uC218', className: 'decision-buy' },
  watch: { emoji: '\uD83D\uDFE1', label: '\uAD00\uCC30', className: 'decision-watch' },
  avoid: { emoji: '\uD83D\uDD34', label: '\uD68C\uD53C', className: 'decision-avoid' },
}

interface DecisionCardProps {
  decision: TickerDecisionData
}

export function DecisionCard({ decision }: DecisionCardProps) {
  const config = ACTION_CONFIG[decision.action] ?? ACTION_CONFIG.watch
  const factorEntries = Object.entries(decision.factors ?? {})
    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))

  return (
    <section className={`decision-card ${config.className}`}>
      <div className="decision-header">
        <span className="decision-action-badge">
          {config.emoji} {config.label}
        </span>
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
  valuation: '\uBC38\uB958',
  momentum: '\uBAA8\uBA58\uD140',
  catalyst_recency: '\uCD09\uB9E4',
  signal_track_record: '\uC2E0\uD638\uC2B9\uB960',
  news_tone: '\uB274\uC2A4\uD1A4',
  regime_adjustment: '\uC2DC\uC7A5\uD658\uACBD',
  earnings_pattern: '\uC2E4\uC801\uD328\uD134',
  fundamentals: '\uD380\uB354\uBA58\uD138',
}
