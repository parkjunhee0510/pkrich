import type { CommitteeAnalysisData, CommitteeRoleData } from '../types'
import { CommitteeBadgeRow } from './CommitteeBadgeRow'

const DETAIL_ROLE_ORDER = ['growth_analyst', 'value_skeptic', 'risk_manager', 'macro_strategist'] as const

const DETAIL_ROLE_LABELS: Record<string, string> = {
  growth_analyst: 'Growth Analyst',
  value_skeptic: 'Value Skeptic',
  risk_manager: 'Risk Manager',
  macro_strategist: 'Macro Strategist',
}

type CommitteeDetailPanelProps = {
  committee?: CommitteeAnalysisData | null
}

function asTrimmedString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function getRoles(committee?: CommitteeAnalysisData | null): Record<string, CommitteeRoleData> {
  const roles = committee?.roles
  return roles && typeof roles === 'object' ? roles : {}
}

function renderRoleSummary(role?: CommitteeRoleData): string {
  if (!role) return '위원회 데이터 없음'
  if (role.valid === false) return asTrimmedString(role.invalid_reason) || '요약 생성 실패'
  return asTrimmedString(role.summary) || '요약 생성 전'
}

function formatStance(value: unknown): string {
  const normalized = asTrimmedString(value)
  if (!normalized) return 'N/A'
  return normalized.replace(/_/g, ' ').replace(/\b\w/g, (match) => match.toUpperCase())
}

function formatConfidence(value?: number): string | null {
  if (typeof value !== 'number' || Number.isNaN(value)) return null
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}% confidence`
}

export function CommitteeDetailPanel({ committee }: CommitteeDetailPanelProps) {
  const roles = getRoles(committee)
  const pm = roles.pm
  const pmConfidence = formatConfidence(pm?.confidence)

  return (
    <section className="ticker-detail-section-shell">
      <div className="committee-detail-panel">
        <div className="committee-pm-card">
          <span className="section-kicker">PM Conclusion</span>
          <div className="committee-pm-header">
            <strong>{formatStance(pm?.stance)}</strong>
            {pmConfidence ? <span className="committee-pm-confidence">{pmConfidence}</span> : null}
          </div>
          <p>{pm?.valid === false ? asTrimmedString(pm.invalid_reason) || '요약 생성 실패' : asTrimmedString(pm?.summary) || '위원회 데이터 없음'}</p>
        </div>
        <CommitteeBadgeRow committee={committee} />
        <div className="committee-role-accordions">
          {DETAIL_ROLE_ORDER.map((roleKey) => {
            const role = roles[roleKey]
            return (
              <details key={roleKey} className="committee-role-accordion">
                <summary>
                  <span className="committee-role-title">{DETAIL_ROLE_LABELS[roleKey]}</span>
                  <span className="committee-role-meta">
                    <span className="committee-role-stance">{formatStance(role?.stance)}</span>
                    {role?.strong_objection ? (
                      <span className="committee-role-objection">Strong Objection</span>
                    ) : null}
                  </span>
                </summary>
                <div className="committee-role-body">
                  <p>{renderRoleSummary(role)}</p>
                </div>
              </details>
            )
          })}
        </div>
      </div>
    </section>
  )
}
