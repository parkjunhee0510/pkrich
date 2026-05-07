import { describe, expect, it } from 'vitest'

import type { TickerAnalysisData } from '../types'
import { buildSearchEvidenceBadge } from './searchEvidenceBadge'

type ConfidenceMeta = NonNullable<TickerAnalysisData['decision']>['confidence_meta']

function makeTicker(confidenceMeta?: ConfidenceMeta): TickerAnalysisData {
  return {
    ticker: 'ALAB',
    name: 'Astera Labs',
    decision: {
      action: 'buy',
      conviction: 72,
      reason: 'Strong growth',
      valid_until: '2026-05-10',
      factors: {},
      confidence_meta: confidenceMeta,
    },
  } as TickerAnalysisData
}

describe('buildSearchEvidenceBadge', () => {
  it('classifies strong, watch, weak, missing, and unavailable evidence', () => {
    expect(buildSearchEvidenceBadge(makeTicker({
      search_evidence_score: 0.82,
      search_quality_gate: { evidence_count: 5, source_diversity: 4 },
    }))).toMatchObject({
      label: 'Evidence strong',
      tone: 'strong',
      score: 0.82,
      detail: 'score 0.82 · sources 4 · items 5',
    })

    expect(buildSearchEvidenceBadge(makeTicker({
      search_evidence_score: 0.62,
      search_quality_gate: { evidence_count: 3, source_diversity: 2 },
    }))).toMatchObject({
      label: 'Evidence watch',
      tone: 'watch',
    })

    expect(buildSearchEvidenceBadge(makeTicker({
      search_evidence_score: 0.41,
      search_quality_gate: {
        would_cap_action: true,
        evidence_count: 1,
        source_diversity: 1,
      },
    }))).toMatchObject({
      label: 'Evidence weak',
      tone: 'weak',
      wouldCapAction: true,
    })

    expect(buildSearchEvidenceBadge(makeTicker({
      search_evidence_score: 0,
      search_quality_gate: { evidence_count: 0, source_diversity: 0 },
    }))).toMatchObject({
      label: 'Evidence missing',
      tone: 'missing',
      detail: 'no recent search evidence',
    })

    expect(buildSearchEvidenceBadge(makeTicker(undefined))).toMatchObject({
      label: 'Evidence unavailable',
      tone: 'unavailable',
      score: null,
      detail: 'search evidence unavailable',
    })
  })
})
