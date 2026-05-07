import type { TickerAnalysisData } from '../types'

export type SearchEvidenceTone = 'strong' | 'watch' | 'weak' | 'missing' | 'unavailable'

export interface SearchEvidenceBadgeData {
  label: string
  detail: string
  className: string
  tone: SearchEvidenceTone
  score: number | null
  sourceDiversity: number
  evidenceCount: number
  wouldCapAction: boolean
}

export function buildSearchEvidenceBadge(ticker: TickerAnalysisData): SearchEvidenceBadgeData {
  const meta = ticker.decision?.confidence_meta
  const score = normalizeScore(meta?.search_evidence_score)
  const gate = meta?.search_quality_gate
  const evidenceCount = normalizeCount(gate?.evidence_count)
  const sourceDiversity = normalizeCount(gate?.source_diversity)
  const wouldCapAction = gate?.would_cap_action === true

  if (score === null) {
    return {
      label: 'Evidence unavailable',
      detail: 'search evidence unavailable',
      className: 'search-evidence-unavailable',
      tone: 'unavailable',
      score: null,
      sourceDiversity,
      evidenceCount,
      wouldCapAction: false,
    }
  }

  if (evidenceCount <= 0) {
    return {
      label: 'Evidence missing',
      detail: 'no recent search evidence',
      className: 'search-evidence-missing',
      tone: 'missing',
      score,
      sourceDiversity,
      evidenceCount,
      wouldCapAction,
    }
  }

  const tone = classifyEvidenceTone(score)
  return {
    label: labelForTone(tone),
    detail: `score ${score.toFixed(2)} · sources ${sourceDiversity} · items ${evidenceCount}`,
    className: `search-evidence-${tone}`,
    tone,
    score,
    sourceDiversity,
    evidenceCount,
    wouldCapAction,
  }
}

function classifyEvidenceTone(score: number): Exclude<SearchEvidenceTone, 'missing' | 'unavailable'> {
  if (score >= 0.75) return 'strong'
  if (score >= 0.55) return 'watch'
  return 'weak'
}

function labelForTone(tone: Exclude<SearchEvidenceTone, 'missing' | 'unavailable'>): string {
  if (tone === 'strong') return 'Evidence strong'
  if (tone === 'watch') return 'Evidence watch'
  return 'Evidence weak'
}

function normalizeScore(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function normalizeCount(value: number | null | undefined): number {
  return typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0
}
