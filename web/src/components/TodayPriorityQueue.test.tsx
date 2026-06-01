import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { TodayPriorityQueueResult } from '../utils/todayPriorityQueue'
import { TodayPriorityQueue } from './TodayPriorityQueue'

function buildQueue(): TodayPriorityQueueResult {
  return {
    items: [
      {
        id: 'today-priority-AMD',
        ticker: 'AMD',
        name: 'Advanced Micro Devices',
        officialAction: 'BUY',
        priorityScore: 91,
        priorityLabel: 'Risk and opportunity review',
        tone: 'negative',
        riskLevel: 'high',
        riskLabel: 'Risk high',
        opportunityLevel: 'high',
        opportunityLabel: 'Opportunity high',
        evidenceStatus: 'not_refreshed',
        evidenceLabel: 'Evidence refresh needed',
        reasons: ['Risk intelligence alert', 'BUY with high conviction'],
        nextCheck: '기회는 강하지만 근거 갱신을 먼저 확인하세요.',
        destination: '/ticker/AMD',
      },
    ],
    asOf: '2026-05-21',
    evidenceHealthLabel: 'Evidence coverage 82%',
    qualityWarnings: ['priority_evidence_not_refreshed'],
    emptyLabel: '오늘 별도 우선 점검 종목 없음',
  }
}

function renderQueue(queue: TodayPriorityQueueResult) {
  return render(
    <MemoryRouter>
      <TodayPriorityQueue queue={queue} />
    </MemoryRouter>,
  )
}

describe('TodayPriorityQueue', () => {
  it('renders priority queue rows with badges and detail links', () => {
    renderQueue(buildQueue())

    expect(screen.getByRole('heading', { name: '오늘 점검 큐' })).toBeInTheDocument()
    const row = screen.getByRole('article', { name: 'AMD Risk and opportunity review' })

    expect(row).toBeInTheDocument()
    expect(row).toHaveClass('today-priority-tone-negative')
    expect(screen.getByRole('link', { name: 'AMD' })).toHaveAttribute('href', '/ticker/AMD')
    expect(screen.getByText('Advanced Micro Devices')).toBeInTheDocument()
    expect(within(row).getByText('Risk high')).toHaveClass('today-priority-badge-risk-high')
    expect(within(row).getByText('Opportunity high')).toHaveClass(
      'today-priority-badge-opportunity-high',
    )
    expect(within(row).getByText('Evidence refresh needed')).toHaveClass(
      'today-priority-badge-evidence-not-refreshed',
    )
    expect(screen.getByText('Risk intelligence alert')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'AMD 상세' })).toHaveAttribute(
      'href',
      '/ticker/AMD',
    )
  })

  it('renders the configured empty state when there are no queue items', () => {
    renderQueue({
      ...buildQueue(),
      items: [],
      qualityWarnings: [],
    })

    expect(screen.getByText('오늘 별도 우선 점검 종목 없음')).toBeInTheDocument()
  })
})
