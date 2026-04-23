import type { CommitteeAnalysisData } from '../types'

type CommitteeBadgeRowProps = {
  committee?: CommitteeAnalysisData | null
}

const AGREEMENT_LABELS: Record<string, string> = {
  aligned: 'Aligned',
  mixed: 'Mixed',
  contested: 'Contested',
}

const REASON_LABELS: Record<string, string> = {
  pm_low_confidence: 'PM Low Confidence',
  risk_strong_objection: 'Risk Objection',
  macro_strong_objection: 'Macro Objection',
}

function asTrimmedString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function hasCommitteePayload(committee?: CommitteeAnalysisData | null): boolean {
  return Boolean(committee && typeof committee === 'object')
}

function formatAgreement(value: unknown): string {
  const normalized = asTrimmedString(value).toLowerCase()
  if (!normalized) return 'N/A'
  return AGREEMENT_LABELS[normalized] ?? normalized.replace(/_/g, ' ')
}

function getAgreementClass(value: unknown): string {
  const normalized = asTrimmedString(value).toLowerCase()
  if (normalized === 'aligned') return 'committee-badge-positive'
  if (normalized === 'contested') return 'committee-badge-deep'
  return 'committee-badge-caution'
}

function normalizeReasons(committee?: CommitteeAnalysisData | null): string[] {
  if (!Array.isArray(committee?.deep_review_reasons)) return []
  return committee.deep_review_reasons
    .filter((reason): reason is string => typeof reason === 'string' && reason.trim().length > 0)
}

function formatReason(reason: string): string {
  return REASON_LABELS[reason] ?? reason.replace(/_/g, ' ')
}

export function CommitteeBadgeRow({ committee }: CommitteeBadgeRowProps) {
  const available = hasCommitteePayload(committee)
  const agreement = formatAgreement(committee?.agreement_status)
  const deep = committee?.deep_review_triggered === true
  const reasons = normalizeReasons(committee)
  const reviewLabel = available ? (deep ? 'Deep Review' : 'Economy Only') : 'Committee Unavailable'

  return (
    <div className="committee-badge-row">
      <span className={`committee-badge committee-badge-agreement ${getAgreementClass(committee?.agreement_status)}`}>
        Agreement {agreement}
      </span>
      <span className={`committee-badge ${available && deep ? 'committee-badge-deep' : 'committee-badge-muted'}`}>
        {reviewLabel}
      </span>
      {reasons.map((reason) => (
        <span key={reason} className="committee-badge committee-badge-reason">
          {formatReason(reason)}
        </span>
      ))}
    </div>
  )
}
