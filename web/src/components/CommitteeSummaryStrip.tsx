import type { CommitteeAnalysisData, CommitteeRoleData } from '../types'
import { CommitteeBadgeRow } from './CommitteeBadgeRow'

const DASHBOARD_ROLE_ORDER = ['growth_analyst', 'value_skeptic', 'risk_manager', 'macro_strategist'] as const

const DASHBOARD_ROLE_LABELS: Record<string, string> = {
  growth_analyst: 'Growth',
  value_skeptic: 'Value',
  risk_manager: 'Risk',
  macro_strategist: 'Macro',
  pm: 'PM',
}

type CommitteeSummaryStripProps = {
  committee?: CommitteeAnalysisData | null
}

function asTrimmedString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function getSummaryText(role?: CommitteeRoleData): string {
  if (!role) return '위원회 데이터 없음'
  if (role.valid === false) return asTrimmedString(role.invalid_reason) || '요약 생성 실패'
  return asTrimmedString(role.summary) || '요약 생성 전'
}

function getPmSummaryText(role?: CommitteeRoleData): string {
  if (!role) return '위원회 데이터 없음'
  if (role.valid === false) return asTrimmedString(role.invalid_reason) || '요약 생성 실패'
  return asTrimmedString(role.summary) || '요약 생성 전'
}

function getRoles(committee?: CommitteeAnalysisData | null): Record<string, CommitteeRoleData> {
  const roles = committee?.roles
  return roles && typeof roles === 'object' ? roles : {}
}

export function CommitteeSummaryStrip({ committee }: CommitteeSummaryStripProps) {
  const roles = getRoles(committee)
  const pm = roles.pm

  return (
    <section className="committee-summary-strip" aria-label="Committee summary">
      <CommitteeBadgeRow committee={committee} />
      <div className="committee-summary-grid">
        {DASHBOARD_ROLE_ORDER.map((roleKey) => (
          <div key={roleKey} className="committee-summary-cell">
            <span className="committee-summary-label">{DASHBOARD_ROLE_LABELS[roleKey]}</span>
            <p>{getSummaryText(roles[roleKey])}</p>
          </div>
        ))}
      </div>
      <div className="committee-pm-summary">
        <span className="committee-summary-label">{DASHBOARD_ROLE_LABELS.pm}</span>
        <p>{getPmSummaryText(pm)}</p>
      </div>
    </section>
  )
}
