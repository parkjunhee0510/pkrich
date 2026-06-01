import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { SearchEvidenceBadge } from '../SearchEvidenceBadge'
import { Badge } from './Badge'

const weakBadge = {
  label: 'Evidence weak',
  detail: 'score 0.41 / sources 1 / items 1',
  className: 'search-evidence-weak',
  tone: 'weak' as const,
  score: 0.41,
  sourceDiversity: 1,
  evidenceCount: 1,
  wouldCapAction: true,
}

describe('Badge primitive', () => {
  it('renders a square shadcn-style badge with variant and custom classes', () => {
    render(
      <Badge variant="outline" className="custom-badge">
        Alpha
      </Badge>,
    )

    const badge = screen.getByText('Alpha')
    expect(badge).toHaveClass('ui-badge')
    expect(badge).toHaveClass('ui-badge-outline')
    expect(badge).toHaveClass('custom-badge')
  })

  it('lets SearchEvidenceBadge reuse the primitive while preserving detail labels', () => {
    render(<SearchEvidenceBadge badge={weakBadge} className="extra-context" />)

    const badge = screen.getByLabelText('score 0.41 / sources 1 / items 1')
    expect(badge).toHaveClass('ui-badge')
    expect(badge).toHaveClass('search-evidence-badge')
    expect(badge).toHaveClass('search-evidence-weak')
    expect(badge).toHaveClass('extra-context')
    expect(badge).toHaveAttribute('title', 'score 0.41 / sources 1 / items 1')
  })
})
