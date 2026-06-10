import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { ActionChangeFeedEntry, ActionChangeFeedResult } from '../utils/actionChangeFeed'
import { ActionChangeFeed } from './ActionChangeFeed'

function makeEntry(overrides: Partial<ActionChangeFeedEntry> = {}): ActionChangeFeedEntry {
  return {
    id: 'action_change-ALAB',
    type: 'action_change',
    tone: 'positive',
    ticker: 'ALAB',
    name: 'Astera Labs',
    sector: 'Technology',
    previousAction: 'watch',
    currentAction: 'buy',
    previousConviction: 52,
    currentConviction: 72,
    convictionDelta: 20,
    addedRisks: ['Valuation risk'],
    primaryLabel: 'WATCH -> BUY',
    secondaryLabel: 'Conviction 52 -> 72 (+20p)',
    qualityDetail: 'quality 0.42',
    qualityClassName: 'today-decision-quality-low',
    metricLabel: '+20p',
    summary: 'AI connectivity momentum improved.',
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
    ...overrides,
  }
}

function makeFeed(
  entries: ActionChangeFeedEntry[],
  overrides: Partial<ActionChangeFeedResult> = {},
): ActionChangeFeedResult {
  return {
    currentDate: '2026-05-01',
    previousDate: '2026-04-29',
    hasPreviousDay: true,
    entries,
    ...overrides,
  }
}

function renderFeed(feed: ActionChangeFeedResult) {
  return render(
    <MemoryRouter>
      <ActionChangeFeed feed={feed} />
    </MemoryRouter>,
  )
}

describe('ActionChangeFeed', () => {
  it('renders action change cards with ticker links and risk badges', () => {
    renderFeed(makeFeed([makeEntry()]))

    expect(screen.getByRole('heading', { name: '오늘 판단 변화' })).toBeInTheDocument()
    expect(screen.getByText('2026-04-29 대비 2026-05-01')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'ALAB' })).toHaveAttribute('href', '/ticker/ALAB')
    expect(screen.getByText('Astera Labs')).toBeInTheDocument()
    expect(screen.getByText('Technology')).toBeInTheDocument()
    expect(screen.getByText('WATCH -> BUY')).toBeInTheDocument()
    const card = screen.getByText('WATCH -> BUY').closest('article')
    expect(card).toHaveClass('action-change-type-action-change')
    expect(card).toHaveClass('action-change-stance-positive')
    expect(card?.className).not.toContain('tone-')
    expect(screen.getByText('WATCH -> BUY')).toHaveClass('action-change-stance-positive')
    expect(screen.getByText('WATCH -> BUY').className).not.toContain('tone-')
    expect(screen.getByText('Conviction 52 -> 72 (+20p)')).toBeInTheDocument()
    expect(screen.getByText('quality 0.42')).toHaveClass('today-decision-quality-low')
    expect(screen.getByText('+20p')).toBeInTheDocument()
    expect(screen.getByText('Evidence weak')).toHaveClass('search-evidence-weak')
    expect(screen.getByText('새 리스크 1개')).toBeInTheDocument()
    expect(screen.getByText('AI connectivity momentum improved.')).toBeInTheDocument()
    expect(screen.getByText('리스크: Valuation risk')).toBeInTheDocument()
  })

  it('renders no previous day empty state', () => {
    renderFeed({
      currentDate: '2026-05-01',
      previousDate: null,
      hasPreviousDay: false,
      entries: [],
    })

    expect(
      screen.getByText('직전 리포트가 없어 변화 비교를 시작할 수 없습니다.'),
    ).toBeInTheDocument()
  })

  it('renders no change empty state', () => {
    renderFeed(makeFeed([]))

    expect(screen.getByText('오늘 공식 판단 변화는 크지 않습니다.')).toBeInTheDocument()
  })

  it('shows the first eight entries before expanding and can collapse again', () => {
    const entries = Array.from({ length: 9 }, (_, index) =>
      makeEntry({
        id: `new_ticker-T${index}`,
        type: 'new_ticker',
        tone: 'info',
        ticker: `T${index}`,
        name: `Ticker ${index}`,
        sector: 'Industrials',
        addedRisks: [],
        primaryLabel: 'NEW WATCH',
        secondaryLabel: 'Conviction 64',
        summary: `Ticker ${index} summary`,
      }),
    )

    renderFeed(makeFeed(entries))

    expect(screen.getByRole('link', { name: 'T0' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'T8' })).not.toBeInTheDocument()

    const expandButton = screen.getByRole('button', { name: '전체 보기' })
    const controlledGridId = expandButton.getAttribute('aria-controls')

    expect(expandButton).toHaveAttribute('aria-expanded', 'false')
    expect(controlledGridId).toBeTruthy()
    expect(document.getElementById(controlledGridId ?? '')).toHaveClass('action-change-grid')

    fireEvent.click(expandButton)

    expect(screen.getByRole('link', { name: 'T8' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '접기' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(screen.getByRole('button', { name: '접기' })).toHaveAttribute(
      'aria-controls',
      controlledGridId,
    )

    fireEvent.click(screen.getByRole('button', { name: '접기' }))

    expect(screen.queryByRole('link', { name: 'T8' })).not.toBeInTheDocument()
  })

  it('collapses expanded entries when the feed identity changes', () => {
    const firstEntries = Array.from({ length: 9 }, (_, index) =>
      makeEntry({
        id: `new_ticker-T${index}`,
        type: 'new_ticker',
        tone: 'info',
        ticker: `T${index}`,
        name: `Ticker ${index}`,
        addedRisks: [],
        primaryLabel: 'NEW WATCH',
        secondaryLabel: 'Conviction 64',
        summary: `Ticker ${index} summary`,
      }),
    )
    const secondEntries = Array.from({ length: 9 }, (_, index) =>
      makeEntry({
        id: `new_ticker-U${index}`,
        type: 'new_ticker',
        tone: 'info',
        ticker: `U${index}`,
        name: `Updated ${index}`,
        addedRisks: [],
        primaryLabel: 'NEW WATCH',
        secondaryLabel: 'Conviction 65',
        summary: `Updated ${index} summary`,
      }),
    )

    const { rerender } = render(
      <MemoryRouter>
        <ActionChangeFeed feed={makeFeed(firstEntries)} />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: '전체 보기' }))

    expect(screen.getByRole('link', { name: 'T8' })).toBeInTheDocument()

    rerender(
      <MemoryRouter>
        <ActionChangeFeed
          feed={makeFeed(secondEntries, {
            currentDate: '2026-05-02',
            previousDate: '2026-05-01',
          })}
        />
      </MemoryRouter>,
    )

    expect(screen.queryByRole('link', { name: 'U8' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '전체 보기' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })
})
