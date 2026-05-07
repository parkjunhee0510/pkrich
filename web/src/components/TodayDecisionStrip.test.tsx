import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { TodayDecisionStripEntry, TodayDecisionStripResult } from '../utils/todayDecisionStrip'
import { TodayDecisionStrip } from './TodayDecisionStrip'

function makeEntry(overrides: Partial<TodayDecisionStripEntry> = {}): TodayDecisionStripEntry {
  return {
    id: 'quality_gate-FLNC',
    kind: 'quality_gate',
    ticker: 'FLNC',
    name: 'Fluence Energy',
    sector: 'Industrials',
    categoryLabel: 'Quality gate',
    title: 'FLNC BUY capped',
    supportingLine: 'cap to WATCH · coverage 0.44',
    qualityLabel: 'low quality',
    qualityScore: 0.52,
    qualityDetail: 'quality 0.52',
    qualityClassName: 'today-decision-quality-low',
    metricLabel: 'cap to WATCH',
    evidenceBadge: {
      label: 'Evidence weak',
      detail: 'score 0.42 · sources 2 · items 2',
      className: 'search-evidence-weak',
      tone: 'weak',
      score: 0.42,
      sourceDiversity: 2,
      evidenceCount: 2,
      wouldCapAction: true,
    },
    stance: 'caution',
    rankScore: 0.52,
    convictionRank: 65,
    ...overrides,
  }
}

function makeStrip(entries: TodayDecisionStripEntry[]): TodayDecisionStripResult {
  return {
    currentDate: '2026-05-01',
    previousDate: '2026-04-29',
    entries,
  }
}

function renderStrip(strip: TodayDecisionStripResult) {
  return render(
    <MemoryRouter>
      <TodayDecisionStrip strip={strip} />
    </MemoryRouter>,
  )
}

describe('TodayDecisionStrip', () => {
  it('renders decision cards with ticker links and quality badges', () => {
    renderStrip(makeStrip([makeEntry()]))

    expect(screen.getByRole('heading', { name: '오늘 먼저 볼 판단' })).toBeInTheDocument()
    expect(screen.getByText('2026-04-29 대비 2026-05-01')).toBeInTheDocument()
    expect(screen.getByText('1개')).toBeInTheDocument()
    expect(screen.getByText('Quality gate')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'FLNC' })).toHaveAttribute('href', '/ticker/FLNC')
    expect(screen.getByText('Fluence Energy')).toBeInTheDocument()
    expect(screen.getByText('FLNC BUY capped')).toBeInTheDocument()
    expect(screen.getByText('low quality')).toHaveClass('today-decision-quality-low')
    expect(screen.getByText('Evidence weak')).toHaveClass('search-evidence-weak')
    expect(screen.getByText('quality 0.52')).toBeInTheDocument()
    expect(screen.getByText('cap to WATCH')).toBeInTheDocument()
  })

  it('uses scoped class names that avoid tone-', () => {
    renderStrip(
      makeStrip([
        makeEntry({
          stance: 'positive',
          qualityClassName: 'today-decision-quality-high',
          qualityLabel: 'high quality',
        }),
      ]),
    )

    const card = screen.getByText('FLNC BUY capped').closest('article')
    const badge = screen.getByText('high quality')

    expect(card).toHaveClass('today-decision-card')
    expect(card).toHaveClass('today-decision-stance-positive')
    expect(card?.className).not.toContain('tone-')
    expect(badge.className).not.toContain('tone-')
  })

  it('renders the empty state when there are no entries', () => {
    renderStrip(makeStrip([]))

    expect(screen.getByText('오늘 우선 확인할 판단 변화가 없습니다.')).toBeInTheDocument()
  })
})
