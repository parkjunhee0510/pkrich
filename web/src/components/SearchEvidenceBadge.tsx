import type { TickerAnalysisData } from '../types'
import { cn } from '../lib/utils'
import {
  buildSearchEvidenceBadge,
  type SearchEvidenceBadgeData,
} from '../utils/searchEvidenceBadge'
import { Badge } from './ui/Badge'

export function SearchEvidenceBadge({
  badge,
  className = '',
}: {
  badge: SearchEvidenceBadgeData
  className?: string
}) {
  return (
    <Badge
      variant="unstyled"
      className={cn('search-evidence-badge', badge.className, className)}
      aria-label={badge.detail}
      title={badge.detail}
    >
      {badge.label}
    </Badge>
  )
}

export function SearchEvidencePanel({ ticker }: { ticker: TickerAnalysisData }) {
  const badge = buildSearchEvidenceBadge(ticker)
  const action = ticker.decision?.action?.toUpperCase() ?? 'ACTION'
  const maxAction = String(
    ticker.decision?.confidence_meta?.search_quality_gate?.max_action_if_enforced ?? 'watch',
  ).toUpperCase()

  return (
    <section className="search-evidence-panel ticker-detail-section-shell">
      <div className="search-evidence-panel-head">
        <div>
          <h3>Search evidence</h3>
          <p className="section-kicker">Normalized web evidence quality for this decision</p>
        </div>
        <SearchEvidenceBadge badge={badge} />
      </div>

      <div className="search-evidence-panel-grid">
        <div className="search-evidence-metric">
          <span>Score</span>
          <strong>{badge.score === null ? 'N/A' : badge.score.toFixed(2)}</strong>
        </div>
        <div className="search-evidence-metric">
          <span>Sources</span>
          <strong>{badge.sourceDiversity}</strong>
        </div>
        <div className="search-evidence-metric">
          <span>Items</span>
          <strong>{badge.evidenceCount}</strong>
        </div>
      </div>

      <p className="search-evidence-detail">{badge.detail}</p>
      {badge.wouldCapAction ? (
        <p className="search-evidence-gate-note">
          Shadow gate: {action} would cap to {maxAction}
        </p>
      ) : null}
    </section>
  )
}
