import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { TickerAnalysisData } from '../types'
import { SearchEvidenceBadge, SearchEvidencePanel } from './SearchEvidenceBadge'

const weakBadge = {
  label: 'Evidence weak',
  detail: 'score 0.41 · sources 1 · items 1',
  className: 'search-evidence-weak',
  tone: 'weak' as const,
  score: 0.41,
  sourceDiversity: 1,
  evidenceCount: 1,
  wouldCapAction: true,
}

describe('SearchEvidenceBadge', () => {
  it('renders compact badge label and accessible detail', () => {
    render(<SearchEvidenceBadge badge={weakBadge} />)

    expect(screen.getByText('Evidence weak')).toHaveClass('search-evidence-weak')
    expect(screen.getByLabelText('score 0.41 · sources 1 · items 1')).toBeInTheDocument()
  })

  it('renders ticker detail panel with gate warning and source counts', () => {
    const ticker = {
      ticker: 'ALAB',
      name: 'Astera Labs',
      decision: {
        action: 'buy',
        conviction: 72,
        reason: 'Strong growth',
        valid_until: '2026-05-10',
        factors: {},
        confidence_meta: {
          search_evidence_score: 0.41,
          search_quality_gate: {
            would_cap_action: true,
            evidence_count: 1,
            source_diversity: 1,
            max_action_if_enforced: 'watch',
          },
        },
      },
    } as unknown as TickerAnalysisData

    render(<SearchEvidencePanel ticker={ticker} />)

    expect(screen.getByRole('heading', { name: 'Search evidence' })).toBeInTheDocument()
    expect(screen.getByText('Evidence weak')).toBeInTheDocument()
    expect(screen.getByText('score 0.41 · sources 1 · items 1')).toBeInTheDocument()
    expect(screen.getByText('Shadow gate: BUY would cap to WATCH')).toBeInTheDocument()
  })
})
