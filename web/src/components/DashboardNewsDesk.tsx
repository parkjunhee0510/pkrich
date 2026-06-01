import { useEffect, useState } from 'react'

import type {
  NewsDeskFeedItem,
  NewsDeskImpactItem,
  NewsDeskMarketMoveItem,
  NewsDeskSituationItem,
  NewsDeskTone,
  NewsDeskViewModel,
} from '../utils/newsDesk'
import { cn } from '../lib/utils'
import { InfoTooltip } from './InfoTooltip'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/Card'
import { EmptyState } from './ui/EmptyState'

const INITIAL_FEED_LIMIT = 6
const COMPACT_FEED_LIMIT = 3
const COMPACT_FEED_QUERY = '(max-width: 640px)'
const FEED_LIST_ID = 'news-desk-feed-list'

type DashboardNewsDeskProps = {
  viewModel: NewsDeskViewModel
  refreshing: boolean
}

function getCompactFeedMatch() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }

  return window.matchMedia(COMPACT_FEED_QUERY).matches
}

function useCompactFeedLayout() {
  const [isCompactFeed, setIsCompactFeed] = useState(getCompactFeedMatch)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return undefined
    }

    const mediaQuery = window.matchMedia(COMPACT_FEED_QUERY)
    const handleChange = () => setIsCompactFeed(mediaQuery.matches)
    handleChange()

    if (typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', handleChange)
      return () => mediaQuery.removeEventListener('change', handleChange)
    }

    if (typeof mediaQuery.addListener === 'function') {
      mediaQuery.addListener(handleChange)
      return () => mediaQuery.removeListener(handleChange)
    }

    return undefined
  }, [])

  return isCompactFeed
}

export function DashboardNewsDesk({ viewModel, refreshing }: DashboardNewsDeskProps) {
  const [expanded, setExpanded] = useState(false)
  const isCompactFeed = useCompactFeedLayout()
  const collapsedFeedLimit = isCompactFeed ? COMPACT_FEED_LIMIT : INITIAL_FEED_LIMIT
  const hasMoreFeedItems = viewModel.feedItems.length > collapsedFeedLimit
  const remainingFeedItemCount = viewModel.feedItems.length - collapsedFeedLimit
  const visibleFeedItems = expanded
    ? viewModel.feedItems
    : viewModel.feedItems.slice(0, collapsedFeedLimit)

  return (
    <section className="news-desk" aria-label="오늘의 뉴스 데스크" data-expanded={expanded ? 'true' : 'false'}>
      <header className="news-desk-header">
        <div className="news-desk-header-copy">
          <p className="news-desk-kicker">오늘의 상황</p>
          <h2>오늘의 상황판</h2>
          <time dateTime={viewModel.date} aria-label={`기준일 ${viewModel.date}`}>
            {viewModel.date}
          </time>
        </div>
        {refreshing ? (
          <p className="news-desk-refresh-status" role="status" aria-live="polite">
            최신 output을 조용히 갱신하는 중입니다.
          </p>
        ) : null}
      </header>

      {viewModel.states.hasDataError ? (
        <div className="news-desk-alert" role="alert">
          <strong>데이터 일부를 불러오지 못했습니다.</strong>
          <p>{viewModel.states.dataErrorMessage ?? '다른 시장 정보는 계속 표시됩니다.'}</p>
        </div>
      ) : null}

      <div className="news-desk-first-grid">
        <Card as="section" className="news-desk-headlines-card" aria-labelledby="news-desk-headlines-title">
          <CardHeader>
            <CardTitle id="news-desk-headlines-title">핵심 문장</CardTitle>
            <CardDescription>오늘 먼저 읽을 시장 변화입니다.</CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="news-desk-headline-list">
              {viewModel.headlines.map((headline) => (
                <li key={headline.id} className={toneClassName('news-desk-headline-item', headline.tone)}>
                  {headline.text}
                </li>
              ))}
            </ol>
            <ul className="news-desk-situation-list" aria-label="시장 상황 요약">
              {viewModel.situation.map((item) => (
                <SituationItem key={item.id} item={item} />
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card as="section" className="news-desk-market-card" aria-labelledby="news-desk-market-title">
          <CardHeader>
            <CardTitle id="news-desk-market-title">시장 변화</CardTitle>
            <CardDescription>지수, 금리, 달러, 유가, 금 흐름입니다.</CardDescription>
          </CardHeader>
          <CardContent>
            {viewModel.marketMoves.length > 0 ? (
              <div className="news-desk-market-grid">
                {viewModel.marketMoves.map((item) => (
                  <MarketMoveItem key={item.id} item={item} />
                ))}
              </div>
            ) : (
              <EmptyState
                title="유가와 금 가격 데이터를 불러오지 못했습니다."
                description="다른 시장 지표는 계속 표시됩니다."
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="news-desk-main-grid">
        <Card as="section" className="news-desk-feed-card" aria-labelledby="news-desk-feed-title">
          <CardHeader>
            <CardTitle id="news-desk-feed-title">뉴스 데스크</CardTitle>
            <CardDescription>뉴스, 리스크, 근거 점검을 영향 순서로 정리합니다.</CardDescription>
          </CardHeader>
          <CardContent>
            {visibleFeedItems.length > 0 ? (
              <ul id={FEED_LIST_ID} className="news-desk-feed-list" aria-label="뉴스 데스크 피드">
                {visibleFeedItems.map((item, index) => (
                  <FeedItem
                    key={item.id}
                    item={item}
                    collapsedMobileExtra={!expanded && isCompactFeed && index >= collapsedFeedLimit}
                  />
                ))}
              </ul>
            ) : (
              <EmptyState title={viewModel.empty.title} description={viewModel.empty.description} />
            )}
            {hasMoreFeedItems ? (
              <button
                type="button"
                className="news-desk-more-button"
                aria-controls={FEED_LIST_ID}
                aria-expanded={expanded}
                aria-label={expanded ? '뉴스 데스크 피드 접기' : `뉴스 데스크 피드 더보기 ${remainingFeedItemCount}개`}
                onClick={() => setExpanded((current) => !current)}
              >
                {expanded ? '접기' : `더보기 ${remainingFeedItemCount}개`}
              </button>
            ) : null}
          </CardContent>
        </Card>

        <Card as="section" className="news-desk-impact-card" aria-labelledby="news-desk-impact-title">
          <CardHeader>
            <CardTitle id="news-desk-impact-title">영향 요약</CardTitle>
            <CardDescription>오늘 확인할 섹터와 종목입니다.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="news-desk-impact-grid">
              <ImpactList title="영향 섹터" items={viewModel.impacts.sectors} />
              <ImpactList title="영향 종목" items={viewModel.impacts.tickers} />
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  )
}

function SituationItem({ item }: { item: NewsDeskSituationItem }) {
  return (
    <li className={toneClassName('news-desk-situation-item', item.tone)}>
      <span className="news-desk-situation-label">{item.label}</span>
      <strong className="news-desk-situation-value">{item.value}</strong>
      <span className="news-desk-situation-detail">{item.detail}</span>
    </li>
  )
}

function MarketMoveItem({ item }: { item: NewsDeskMarketMoveItem }) {
  return (
    <article className={toneClassName('news-desk-market-item', item.tone)}>
      <div className="news-desk-market-item-header">
        <h4>{item.label}</h4>
        <InfoTooltip content={getMarketMoveTooltipContent(item)} />
      </div>
      <strong className="news-desk-market-value">{item.value}</strong>
      <span className="news-desk-market-change">{item.change}</span>
    </article>
  )
}

function getMarketMoveTooltipContent(item: NewsDeskMarketMoveItem) {
  const key = `${item.id} ${item.label}`.toLowerCase()
  const label = item.label.trim().toLowerCase()

  if (key.includes('s&p') || key.includes('sp500') || key.includes('snp')) {
    return '상승: 시장 전반의 위험자산 선호. 하락: 광범위한 경계심 또는 차익실현 압력.'
  }

  if (key.includes('nasdaq') || key.includes('나스닥')) {
    return '상승: 성장주와 기술주 선호. 하락: 금리 부담 확대나 성장주 회피.'
  }

  if (key.includes('vix')) {
    return '상승: 변동성 기대와 불안 확대. 하락: 공포 완화와 위험자산 선호 회복.'
  }

  if (key.includes('oil') || key.includes('wti') || key.includes('유가')) {
    return '상승: 에너지 비용과 인플레 부담 확대. 하락: 수요 둔화 우려 또는 비용 부담 완화.'
  }

  if (key.includes('dollar') || key.includes('dxy') || key.includes('달러')) {
    return '상승: 미국 자산 선호와 유동성 부담. 하락: 위험자산과 원자재에 우호적.'
  }

  if (key.includes('10y') || key.includes('us10') || key.includes('10년') || key.includes('금리')) {
    return '상승: 할인율 부담 확대. 하락: 성장주와 금리 민감 자산에 우호적.'
  }

  if (key.includes('gold') || label === '금' || label.includes('금 가격')) {
    return '상승: 안전자산 선호, 실질금리 하락, 달러 약세. 하락: 위험선호 회복 또는 금리 부담.'
  }

  if (key.includes('copper') || key.includes('구리')) {
    return '상승: 제조업과 인프라 수요 기대. 하락: 경기 둔화 또는 중국 수요 약화.'
  }

  return '상승과 하락은 관련 섹터, 금리, 달러 흐름과 함께 해석하세요.'
}

function FeedItem({ item, collapsedMobileExtra }: { item: NewsDeskFeedItem; collapsedMobileExtra: boolean }) {
  return (
    <li
      className={cn(
        toneClassName('news-desk-feed-item', item.tone),
        collapsedMobileExtra && 'news-desk-feed-mobile-extra',
      )}
    >
      <article>
        <div className="news-desk-feed-meta">
          <span className="news-desk-feed-category">{item.categoryLabel}</span>
          <span className="news-desk-feed-priority">{item.priority}</span>
        </div>
        <h4>{item.title}</h4>
        <p>{item.whyItMatters}</p>
        <dl className="news-desk-feed-details">
          <div>
            <dt>영향 범위</dt>
            <dd>{item.affectedLabel}</dd>
          </div>
          <div>
            <dt>오늘 확인</dt>
            <dd>{item.todayCheck}</dd>
          </div>
        </dl>
      </article>
    </li>
  )
}

function ImpactList({ title, items }: { title: string; items: NewsDeskImpactItem[] }) {
  const titleId = `news-desk-impact-${stableTitleId(title)}`

  return (
    <section className="news-desk-impact-list-section" aria-labelledby={titleId}>
      <h4 id={titleId}>{title}</h4>
      {items.length > 0 ? (
        <ul className="news-desk-impact-list">
          {items.map((item) => (
            <li key={item.id} className={toneClassName('news-desk-impact-item', item.tone)}>
              {item.ticker && item.ticker !== item.label ? (
                <span className="news-desk-impact-ticker">{item.ticker}</span>
              ) : null}
              <strong>{item.label}</strong>
              <p>{item.detail}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="news-desk-impact-empty">오늘 별도 영향 항목은 없습니다.</p>
      )}
    </section>
  )
}

function toneClassName(base: string, tone: NewsDeskTone) {
  return `${base} ${base}-${tone}`
}

function stableTitleId(title: string) {
  return title.replace(/\s+/g, '-')
}
