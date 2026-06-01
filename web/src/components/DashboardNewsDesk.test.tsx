import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  NewsDeskFeedItem,
  NewsDeskImpactItem,
  NewsDeskMarketMoveItem,
  NewsDeskSituationItem,
  NewsDeskTone,
  NewsDeskViewModel,
} from '../utils/newsDesk'
import { DashboardNewsDesk } from './DashboardNewsDesk'

const positiveTone: NewsDeskTone = 'positive'
const originalMatchMedia = window.matchMedia

afterEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: originalMatchMedia,
  })
})

function mockCompactFeedMedia(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(max-width: 640px)' ? matches : false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

function makeSituation(overrides: Partial<NewsDeskSituationItem> = {}): NewsDeskSituationItem {
  return {
    id: 'market-mood',
    label: '시장 분위기',
    value: '위험자산 선호',
    detail: '대형 기술주와 반도체가 지수를 끌어올렸습니다.',
    tone: positiveTone,
    ...overrides,
  }
}

function makeMarketMove(overrides: Partial<NewsDeskMarketMoveItem> = {}): NewsDeskMarketMoveItem {
  return {
    id: 'real-asset-oil-wti',
    label: '유가 WTI',
    value: '$78.20',
    change: '+1.2%',
    directionLabel: '상승' as NewsDeskMarketMoveItem['directionLabel'],
    tone: 'warning',
    ...overrides,
  }
}

function makeFeedItem(overrides: Partial<NewsDeskFeedItem> = {}): NewsDeskFeedItem {
  return {
    id: 'risk-supply-chain',
    category: 'risk',
    categoryLabel: '리스크',
    title: '공급망 리스크 확인 필요',
    whyItMatters: '반도체 장비 공급 지연이 실적 기대에 영향을 줄 수 있습니다.',
    affectedLabel: '반도체 / AMD',
    todayCheck: 'AMD와 주요 장비주의 가격 반응을 확인하세요.',
    tone: 'warning',
    priority: 95,
    ...overrides,
  }
}

function makeImpact(overrides: Partial<NewsDeskImpactItem> = {}): NewsDeskImpactItem {
  return {
    id: 'impact-semiconductors',
    label: '반도체',
    detail: 'AI 서버 수요와 공급망 리스크를 함께 확인합니다.',
    tone: 'positive',
    ...overrides,
  }
}

function makeViewModel(overrides: Partial<NewsDeskViewModel> = {}): NewsDeskViewModel {
  return {
    date: '2026-05-28',
    headlines: [
      {
        id: 'headline-market-mood',
        text: '오늘 시장 분위기는 위험자산 선호입니다.',
        tone: positiveTone,
      },
    ],
    situation: [
      makeSituation(),
      makeSituation({
        id: 'breadth',
        label: '상승 확산도',
        value: '확산',
        detail: '상승 종목 참여가 넓습니다.',
        tone: 'neutral',
      }),
    ],
    marketMoves: [
      makeMarketMove(),
      makeMarketMove({
        id: 'real-asset-gold',
        label: '금',
        value: '$2,360',
        change: '-0.4%',
        directionLabel: '하락' as NewsDeskMarketMoveItem['directionLabel'],
        tone: 'negative',
      }),
    ],
    feedItems: [makeFeedItem()],
    impacts: {
      sectors: [makeImpact()],
      tickers: [
        makeImpact({
          id: 'impact-amd',
          label: 'AMD',
          detail: '다음 실적 가이던스와 뉴스 근거를 점검합니다.',
          ticker: 'AMD',
          tone: 'info',
        }),
      ],
    },
    empty: {
      title: '오늘 크게 올라온 뉴스 데스크 항목은 없습니다.',
      description: '시장 변화와 근거는 계속 확인하고 있습니다.',
    },
    states: {
      hasPartialData: false,
      hasDataError: false,
      dataErrorMessage: null,
      hasEvidenceWarning: false,
    },
    ...overrides,
  }
}

describe('DashboardNewsDesk', () => {
  it('renders the news desk region, situation board, market moves, feed, and impacts', () => {
    render(<DashboardNewsDesk viewModel={makeViewModel()} refreshing={false} />)

    const region = screen.getByRole('region', { name: '오늘의 뉴스 데스크' })
    expect(region).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '오늘의 상황판' })).toBeInTheDocument()
    expect(screen.getByText('오늘 시장 분위기는 위험자산 선호입니다.')).toBeInTheDocument()

    const situationList = screen.getByLabelText('시장 상황 요약')
    expect(within(situationList).getByText('시장 분위기')).toBeInTheDocument()
    expect(within(situationList).getByText('위험자산 선호')).toBeInTheDocument()

    expect(screen.getByText('유가 WTI')).toBeInTheDocument()
    expect(screen.getByText('금')).toBeInTheDocument()
    expect(
      screen.getByRole('button', {
        name: /상승: 에너지 비용과 인플레 부담 확대/,
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', {
        name: /하락: 위험선호 회복 또는 금리 부담/,
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '뉴스 데스크' })).toBeInTheDocument()

    const feed = screen.getByRole('list', { name: '뉴스 데스크 피드' })
    expect(within(feed).getByText('공급망 리스크 확인 필요')).toBeInTheDocument()

    expect(screen.getByRole('heading', { name: '영향 섹터' })).toBeInTheDocument()
    expect(screen.getByText('반도체')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '영향 종목' })).toBeInTheDocument()
    expect(screen.getByText('AMD')).toBeInTheDocument()
  })

  it('uses the market move top-right slot for the tooltip instead of direction text', () => {
    const { container } = render(<DashboardNewsDesk viewModel={makeViewModel()} refreshing={false} />)

    expect(container.querySelector('.news-desk-market-direction')).toBeNull()
    expect(container.querySelectorAll('.news-desk-market-item-header > .info-tooltip')).toHaveLength(2)
  })

  it('uses separate tooltip copy for gold and US 10-year yield', () => {
    render(
      <DashboardNewsDesk
        viewModel={makeViewModel({
          marketMoves: [
            makeMarketMove({
              id: 'real-asset-gold',
              label: '금',
              value: '4,418.80',
              change: '-0.65%',
              directionLabel: '하락' as NewsDeskMarketMoveItem['directionLabel'],
              tone: 'negative',
            }),
            makeMarketMove({
              id: 'macro-us10y',
              label: '미국 10년 금리',
              value: '4.48',
              change: '-0.27%',
              directionLabel: '하락' as NewsDeskMarketMoveItem['directionLabel'],
              tone: 'negative',
            }),
          ],
        })}
        refreshing={false}
      />,
    )

    expect(screen.getByRole('button', { name: /상승: 안전자산 선호/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /상승: 할인율 부담 확대/ })).toBeInTheDocument()
  })

  it('renders a partial data alert while keeping feed content usable', () => {
    render(
      <DashboardNewsDesk
        viewModel={makeViewModel({
          states: {
            hasPartialData: true,
            hasDataError: true,
            dataErrorMessage: '거시 데이터 제공자가 응답하지 않았습니다.',
            hasEvidenceWarning: false,
          },
        })}
        refreshing={false}
      />,
    )

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('데이터 일부를 불러오지 못했습니다.')
    expect(alert).toHaveTextContent('거시 데이터 제공자가 응답하지 않았습니다.')
    expect(screen.getByText('공급망 리스크 확인 필요')).toBeInTheDocument()
  })

  it('announces refresh state politely', () => {
    render(<DashboardNewsDesk viewModel={makeViewModel()} refreshing />)

    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('최신 output을 조용히 갱신하는 중입니다.')
    expect(status).toHaveAttribute('aria-live', 'polite')
  })

  it('renders the empty feed state when there are no feed items', () => {
    const viewModel = makeViewModel({ feedItems: [] })

    render(<DashboardNewsDesk viewModel={viewModel} refreshing={false} />)

    expect(screen.getByText(viewModel.empty.title)).toBeInTheDocument()
    expect(screen.getByText(viewModel.empty.description)).toBeInTheDocument()
  })

  it('expands and collapses the feed when more than six items are available', () => {
    const feedItems = Array.from({ length: 7 }, (_, index) => (
      makeFeedItem({
        id: `feed-${index + 1}`,
        title: `뉴스 항목 ${index + 1}`,
        priority: 100 - index,
      })
    ))

    render(<DashboardNewsDesk viewModel={makeViewModel({ feedItems })} refreshing={false} />)

    const feed = screen.getByRole('list', { name: '뉴스 데스크 피드' })
    const moreButton = screen.getByRole('button', { name: '뉴스 데스크 피드 더보기 1개' })
    expect(feed).toHaveAttribute('id', 'news-desk-feed-list')
    expect(moreButton).toHaveAttribute('aria-controls', 'news-desk-feed-list')
    expect(moreButton).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('뉴스 항목 7')).not.toBeInTheDocument()

    fireEvent.click(moreButton)

    const collapseButton = screen.getByRole('button', { name: '뉴스 데스크 피드 접기' })
    expect(collapseButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('뉴스 항목 7')).toBeInTheDocument()

    fireEvent.click(collapseButton)

    const collapsedButton = screen.getByRole('button', { name: '뉴스 데스크 피드 더보기 1개' })
    expect(collapsedButton).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('뉴스 항목 7')).not.toBeInTheDocument()
  })
  it('uses a three-item collapsed feed limit on compact screens', () => {
    mockCompactFeedMedia(true)
    const feedItems = Array.from({ length: 5 }, (_, index) => (
      makeFeedItem({
        id: `mobile-feed-${index + 1}`,
        title: `Mobile feed item ${index + 1}`,
        priority: 100 - index,
      })
    ))

    render(<DashboardNewsDesk viewModel={makeViewModel({ feedItems })} refreshing={false} />)

    const moreButton = screen.getByRole('button', { name: '뉴스 데스크 피드 더보기 2개' })
    expect(moreButton).toHaveAccessibleName('뉴스 데스크 피드 더보기 2개')
    expect(moreButton).toHaveTextContent('2')
    expect(moreButton).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Mobile feed item 4')).not.toBeInTheDocument()
    expect(screen.queryByText('Mobile feed item 5')).not.toBeInTheDocument()

    fireEvent.click(moreButton)

    const collapseButton = screen.getByRole('button', { name: '뉴스 데스크 피드 접기' })
    expect(collapseButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Mobile feed item 5')).toBeInTheDocument()

    fireEvent.click(collapseButton)

    expect(screen.queryByText('Mobile feed item 5')).not.toBeInTheDocument()
  })

})
