import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { TodayPriorityQueueItem } from '../utils/todayPriorityQueue'
import { TickerResearchBrief } from './TickerResearchBrief'

describe('TickerResearchBrief', () => {
  it('renders the selected ticker review context', () => {
    render(<TickerResearchBrief ticker="AMD" item={buildItem()} />)

    expect(screen.getByRole('heading', { name: '오늘 올라온 이유' })).toBeInTheDocument()
    expect(screen.getByText('리스크/기회 동시 점검')).toBeInTheDocument()
    expect(screen.getByText('리스크 인텔 알림')).toBeInTheDocument()
    expect(screen.getByText('높은 확신도의 BUY 판단')).toBeInTheDocument()
    expect(screen.queryByText('Risk intelligence alert')).not.toBeInTheDocument()
    expect(screen.getByText('기회는 강하지만 근거 갱신을 먼저 확인하세요.')).toBeInTheDocument()
  })

  it('renders a neutral fallback when the ticker is not in the queue', () => {
    render(<TickerResearchBrief ticker="KO" item={null} />)

    expect(screen.getByText('오늘 우선 점검 큐에는 포함되지 않았습니다.')).toBeInTheDocument()
    expect(screen.getByText('공식 판단과 기존 상세 데이터를 기준으로 확인하세요.')).toBeInTheDocument()
  })
})

function buildItem(): TodayPriorityQueueItem {
  return {
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
  }
}
