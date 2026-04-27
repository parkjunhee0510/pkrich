import type { DailyEntry, PMPriorityQueueItem, TickerAnalysisData } from '../types'
import { computeSetupScore, getLatestCatalystItem, getNextEarningsEvent } from './trader'

export type CommandQueueTone = 'urgent' | 'watch' | 'info' | 'quiet'
export type CommandQueueSource = 'pm' | 'fallback'
export type CommandWorkspaceTone = 'pm' | 'trader' | 'market' | 'system'

export interface CommandQueueItem {
  id: string
  title: string
  typeLabel: string
  ticker?: string
  relatedTicker?: string
  score?: number
  summary: string
  reasons: string[]
  destination: string
  tone: CommandQueueTone
  source: CommandQueueSource
}

export interface CommandQueueCounts {
  urgent: number
  watch: number
  info: number
}

export interface CommandWorkspaceCardModel {
  id: 'pm' | 'trader' | 'market' | 'system'
  title: string
  eyebrow: string
  summary: string
  metric: string
  href: string
  tone: CommandWorkspaceTone
  disabled?: boolean
}

export interface CommandDeskModel {
  asOf: string
  marketLabel: string
  queueItems: CommandQueueItem[]
  counts: CommandQueueCounts
  workspaces: CommandWorkspaceCardModel[]
  emptyTitle: string
  emptyBody: string
}

export function buildCommandDeskModel(day: DailyEntry, sortedTickers: TickerAnalysisData[]): CommandDeskModel {
  const queueItems = buildCommandQueueItems(day, sortedTickers)
  return {
    asOf: day.pm_view?.as_of || day.date,
    marketLabel: buildMarketLabel(day),
    queueItems,
    counts: countQueueItems(queueItems),
    workspaces: buildWorkspaceCards(day, sortedTickers),
    emptyTitle: '오늘 바로 처리할 우선순위가 없습니다.',
    emptyBody: '보유 리스크, 실적 일정, 강한 재료가 조용한 날입니다. 워치리스트와 시스템 상태를 가볍게 확인하세요.',
  }
}

export function buildCommandQueueItems(day: DailyEntry, sortedTickers: TickerAnalysisData[]): CommandQueueItem[] {
  const pmItems = (day.pm_view?.today_priority_queue ?? []).slice(0, 6).map(mapPmPriorityItem)
  if (pmItems.length > 0) {
    return pmItems
  }
  return buildFallbackQueueItems(sortedTickers)
}

function mapPmPriorityItem(item: PMPriorityQueueItem, index: number): CommandQueueItem {
  return {
    id: `pm-${item.priority_type}-${item.ticker}-${item.related_ticker ?? 'none'}-${index}`,
    title: formatQueueTitle(item),
    typeLabel: priorityLabel(item.priority_type),
    ticker: item.ticker,
    relatedTicker: item.related_ticker ?? undefined,
    score: item.today_priority_score,
    summary: item.summary,
    reasons: item.reasons.filter(Boolean).slice(0, 3),
    destination: normalizeDestination(item.destination, item.ticker),
    tone: priorityTone(item.priority_type, item.today_priority_score),
    source: 'pm',
  }
}

function buildFallbackQueueItems(sortedTickers: TickerAnalysisData[]): CommandQueueItem[] {
  return sortedTickers
    .map((ticker): CommandQueueItem | null => {
      const setup = computeSetupScore(ticker)
      const catalyst = getLatestCatalystItem(ticker)
      const earnings = getNextEarningsEvent(ticker)
      const earningsDays = parseEventDays(earnings?.days_until)
      const isUrgent = catalyst?.level === 'hard' || (Number.isFinite(earningsDays) && earningsDays <= 3)
      const isWatch = setup.score >= 60 || catalyst?.level === 'medium' || (Number.isFinite(earningsDays) && earningsDays <= 7)

      if (!isUrgent && !isWatch) {
        return null
      }

      const reasons = [
        catalyst ? `${catalyst.tag} · ${catalyst.source}` : '',
        earnings ? `${earnings.label} D-${earnings.days_until}${earnings.timing ? ` · ${earnings.timing}` : ''}` : '',
        setup.tags.slice(0, 2).join(' · '),
      ].filter(Boolean)

      return {
        id: `fallback-${ticker.ticker}`,
        title: `${ticker.ticker} 확인`,
        typeLabel: isUrgent ? '긴급 확인' : '관찰 우선',
        ticker: ticker.ticker,
        score: ticker.decision?.conviction ?? setup.score,
        summary: ticker.signal_or_takeaway || ticker.summary || '오늘 신호를 다시 확인하세요.',
        reasons,
        destination: `/ticker/${ticker.ticker}`,
        tone: isUrgent ? 'urgent' : 'watch',
        source: 'fallback',
      } satisfies CommandQueueItem
    })
    .filter((item): item is CommandQueueItem => item !== null)
    .sort((left, right) => (right.score ?? 0) - (left.score ?? 0))
    .slice(0, 6)
}

function buildWorkspaceCards(day: DailyEntry, sortedTickers: TickerAnalysisData[]): CommandWorkspaceCardModel[] {
  const pmView = day.pm_view
  const pmCount =
    (pmView?.swap_candidates?.length ?? 0) +
    (pmView?.event_exposure_items?.length ?? 0) +
    (pmView?.today_priority_queue?.length ?? 0)
  const topSetup = sortedTickers[0]
  const hardCatalysts = day.tickers.filter((ticker) => getLatestCatalystItem(ticker)?.level === 'hard').length
  const earningsSoon = day.tickers.filter((ticker) => {
    const days = parseEventDays(getNextEarningsEvent(ticker)?.days_until)
    return Number.isFinite(days) && days <= 7
  }).length
  const marketRegime = day.market_regime?.regime || '시장 상태 대기'
  const overviewCount = day.market_overview?.length ?? 0

  return [
    {
      id: 'pm',
      title: 'PM Review',
      eyebrow: '보유 리스크',
      summary: pmCount > 0 ? '교체 후보, 이벤트 노출, PM 우선순위를 확인합니다.' : '오늘 PM 전용 경고는 조용합니다.',
      metric: pmCount > 0 ? `${pmCount}건` : '안정',
      href: '/portfolio',
      tone: 'pm',
    },
    {
      id: 'trader',
      title: 'Trader Setups',
      eyebrow: '진입 후보',
      summary: topSetup ? `${topSetup.ticker} 중심으로 강한 재료와 실적 임박 후보를 봅니다.` : '표시할 트레이더 후보가 없습니다.',
      metric: `${hardCatalysts} hard · ${earningsSoon} D-7`,
      href: '#watchlist',
      tone: 'trader',
      disabled: !topSetup,
    },
    {
      id: 'market',
      title: 'Market Context',
      eyebrow: '장세 맥락',
      summary: day.market_regime?.implication || '매크로, 섹터, 시장 지표를 함께 확인합니다.',
      metric: marketRegime,
      href: '#market-context',
      tone: 'market',
      disabled: !day.market_regime && overviewCount === 0,
    },
    {
      id: 'system',
      title: 'System Health',
      eyebrow: '운영 상태',
      summary: 'API 상태, 품질, 비용, 백테스트 화면으로 이동합니다.',
      metric: 'Ops',
      href: '/api-status',
      tone: 'system',
    },
  ]
}

function countQueueItems(items: CommandQueueItem[]): CommandQueueCounts {
  return items.reduce(
    (counts, item) => {
      if (item.tone === 'urgent') counts.urgent += 1
      else if (item.tone === 'watch') counts.watch += 1
      else counts.info += 1
      return counts
    },
    { urgent: 0, watch: 0, info: 0 },
  )
}

function buildMarketLabel(day: DailyEntry): string {
  if (day.market_regime?.regime) {
    return day.market_regime.regime
  }
  const firstOverview = day.market_overview?.[0]
  if (firstOverview) {
    return `${firstOverview.label} ${firstOverview.change}`
  }
  return '시장 맥락 대기'
}

function formatQueueTitle(item: PMPriorityQueueItem): string {
  if (item.related_ticker) {
    return `${item.ticker} ↔ ${item.related_ticker}`
  }
  return `${item.ticker} 확인`
}

function priorityLabel(priorityType: string): string {
  if (priorityType === 'swap_review') return '교체 검토'
  if (priorityType === 'event_review') return '이벤트 점검'
  if (priorityType === 'decision_change') return '판단 변화'
  if (priorityType === 'risk_warning') return '리스크 점검'
  return '오늘 확인'
}

function priorityTone(priorityType: string, score: number): CommandQueueTone {
  if (priorityType === 'event_review' || priorityType === 'risk_warning' || score >= 80) {
    return 'urgent'
  }
  if (priorityType === 'swap_review' || score >= 60) {
    return 'watch'
  }
  return 'info'
}

function normalizeDestination(destination: string, ticker: string): string {
  if (destination.startsWith('/')) return destination
  if (destination === 'portfolio') return '/portfolio'
  return `/ticker/${ticker}`
}

function parseEventDays(value?: string): number {
  if (!value) return Number.POSITIVE_INFINITY
  const parsed = Number.parseInt(value, 10)
  return Number.isNaN(parsed) ? Number.POSITIVE_INFINITY : parsed
}
