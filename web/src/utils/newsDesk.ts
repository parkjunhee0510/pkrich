import type {
  DailyEntry,
  MacroContext,
  MarketOverviewEntry,
  MarketRegimeData,
  QualityReliabilityLoopPayload,
  RiskIntelSummaryCard,
  RiskIntelSummaryPayload,
  SearchEvidencePayload,
  TickerAnalysisData,
} from '../types'
import type { ActionChangeFeedResult } from './actionChangeFeed'
import type { SectorMoodResult } from './sectorMood'
import type { TodayDecisionStripResult } from './todayDecisionStrip'
import type { TodayPriorityQueueResult } from './todayPriorityQueue'

export type NewsDeskTone = 'positive' | 'negative' | 'warning' | 'info' | 'neutral'
export type NewsDeskCategory = 'market' | 'macro' | 'risk' | 'news' | 'evidence' | 'ticker'

export interface NewsDeskHeadline {
  id: string
  text: string
  tone: NewsDeskTone
}

export interface NewsDeskSituationItem {
  id: string
  label: string
  value: string
  detail: string
  tone: NewsDeskTone
}

export interface NewsDeskMarketMoveItem {
  id: string
  label: string
  value: string
  change: string
  directionLabel: '상승' | '하락' | '안정' | '혼조' | '확인 필요'
  tone: NewsDeskTone
}

export interface NewsDeskFeedItem {
  id: string
  category: NewsDeskCategory
  categoryLabel: string
  title: string
  whyItMatters: string
  affectedLabel: string
  todayCheck: string
  tone: NewsDeskTone
  priority: number
}

export interface NewsDeskImpactItem {
  id: string
  label: string
  detail: string
  tone: NewsDeskTone
  ticker?: string
}

export interface NewsDeskViewModel {
  date: string
  headlines: NewsDeskHeadline[]
  situation: NewsDeskSituationItem[]
  marketMoves: NewsDeskMarketMoveItem[]
  feedItems: NewsDeskFeedItem[]
  impacts: {
    sectors: NewsDeskImpactItem[]
    tickers: NewsDeskImpactItem[]
  }
  empty: {
    title: string
    description: string
  }
  states: {
    hasPartialData: boolean
    hasDataError: boolean
    dataErrorMessage: string | null
    hasEvidenceWarning: boolean
  }
}

export interface BuildDashboardNewsDeskInput {
  day: DailyEntry
  previousDay?: DailyEntry | null
  sectorMood?: SectorMoodResult | null
  actionChangeFeed?: ActionChangeFeedResult | null
  todayDecisionStrip?: TodayDecisionStripResult | null
  todayPriorityQueue?: TodayPriorityQueueResult | null
  riskIntelSummary?: RiskIntelSummaryPayload | null
  searchEvidence?: SearchEvidencePayload | null
  qualityLoop?: QualityReliabilityLoopPayload | null
  dataError?: string | null
  limit?: number
}

const DEFAULT_FEED_LIMIT = 6

const REGIME_LABELS: Record<MarketRegimeData['regime'], string> = {
  risk_on: '위험자산 선호',
  risk_off: '안전자산 선호',
  neutral: '중립',
  reflation: '경기민감 자산 선호',
  defensive_bias: '방어적 시장',
}

const CATEGORY_LABELS: Record<NewsDeskCategory, string> = {
  market: '시장 변화',
  macro: '매크로',
  risk: '리스크',
  news: '뉴스',
  evidence: '근거 점검',
  ticker: '종목 변화',
}

const CATEGORY_RANK: Record<NewsDeskCategory, number> = {
  risk: 0,
  evidence: 1,
  macro: 2,
  ticker: 3,
  news: 4,
  market: 5,
}

const MACRO_EVENT_TYPE_LABELS: Record<string, string> = {
  middle_east_escalation: '중동 확전 리스크',
  hormuz_disruption: '호르무즈 해협 차질',
  opec_supply_shock: 'OPEC 공급 충격',
}

export function marketRegimeLabel(regime?: MarketRegimeData['regime'] | string | null): string {
  if (!regime) return '확인 필요'
  return REGIME_LABELS[regime as MarketRegimeData['regime']] ?? '확인 필요'
}

export function buildDashboardNewsDeskViewModel(input: BuildDashboardNewsDeskInput): NewsDeskViewModel {
  const marketMoves = buildMarketMoveItems(input.day)
  const hasEvidenceWarning = hasEvidenceWarningState(input.searchEvidence)
  const feedItems = buildFeedItems(input, marketMoves)
  const impacts = buildImpacts(input)

  return {
    date: input.day.date,
    headlines: buildHeadlines(input, marketMoves, feedItems),
    situation: buildSituation(input.day),
    marketMoves,
    feedItems,
    impacts,
    empty: {
      title: '오늘 크게 달라진 시장 이슈는 없습니다.',
      description: '시장 변화와 점검 큐는 계속 확인할 수 있습니다.',
    },
    states: {
      hasPartialData: isPartialData(input.day, input.sectorMood),
      hasDataError: Boolean(input.dataError),
      dataErrorMessage: input.dataError ?? null,
      hasEvidenceWarning,
    },
  }
}

export function buildMarketMoveItems(day: DailyEntry): NewsDeskMarketMoveItem[] {
  return [
    ...(day.market_overview ?? [])
      .map(buildMarketOverviewMove)
      .filter((item): item is NewsDeskMarketMoveItem => item !== null),
    ...buildMacroMoveItems(day.macro_context),
  ]
}

function buildSituation(day: DailyEntry): NewsDeskSituationItem[] {
  const regime = day.market_regime
  const drivers = Object.values(regime?.drivers ?? {}).filter(isNonEmpty)
  const breadthDriver = drivers.find((driver) => includesAny(driver, ['breadth', '확산', '혼조']))

  return [
    {
      id: 'market-mood',
      label: '시장 분위기',
      value: marketRegimeLabel(regime?.regime),
      detail: firstNonEmpty([regime?.implication, drivers[0], '시장 분위기 데이터 확인 필요']),
      tone: toneFromRegime(regime?.regime),
    },
    {
      id: 'breadth',
      label: '상승 확산도',
      value: breadthLabel(breadthDriver),
      detail: breadthDriver ?? '종목별 참여도 확인',
      tone: 'neutral',
    },
    {
      id: 'volatility',
      label: '변동성',
      value: volatilityLabel(day.macro_context),
      detail: day.macro_context?.vix?.change ?? '변동성 지표 확인',
      tone: volatilityTone(day.macro_context),
    },
  ]
}

function buildHeadlines(
  input: BuildDashboardNewsDeskInput,
  marketMoves: NewsDeskMarketMoveItem[],
  feedItems: NewsDeskFeedItem[],
): NewsDeskHeadline[] {
  const regime = input.day.market_regime?.regime
  const topMove = marketMoves[0]
  const topActionFeed = feedItems.find((item) => item.category !== 'evidence')
  const priorityTicker = input.todayPriorityQueue?.items[0]?.ticker
  const actionText = priorityTicker
    ? `${priorityTicker}를 오늘 우선 확인하세요.`
    : topActionFeed?.todayCheck ?? '오늘 우선 확인할 종목은 많지 않습니다.'

  return [
    {
      id: 'headline-market-mood',
      text: `오늘 시장 분위기는 ${marketRegimeLabel(regime)}입니다.`,
      tone: toneFromRegime(regime),
    },
    {
      id: 'headline-market-move',
      text: topMove
        ? `${topMove.label}는 ${topMove.directionLabel} 흐름입니다.`
        : '시장 변화 데이터는 일부만 확인됩니다.',
      tone: topMove?.tone ?? 'neutral',
    },
    {
      id: 'headline-action',
      text: actionText,
      tone: priorityTicker ? 'info' : topActionFeed?.tone ?? 'info',
    },
  ]
}

function buildFeedItems(
  input: BuildDashboardNewsDeskInput,
  marketMoves: NewsDeskMarketMoveItem[],
): NewsDeskFeedItem[] {
  const candidates = [
    ...buildRiskFeedItems(input.riskIntelSummary),
    ...buildEvidenceFeedItems(input.searchEvidence, input.qualityLoop),
    ...buildMacroFeedItems(input.day.macro_context),
    ...buildActionFeedItems(input.actionChangeFeed),
    ...buildTickerNewsItems(input.day.tickers),
    ...buildMarketMoveFeedItems(marketMoves),
  ]

  return dedupeById(candidates)
    .sort(compareFeedItems)
    .slice(0, resolveLimit(input.limit))
}

function buildRiskFeedItems(summary?: RiskIntelSummaryPayload | null): NewsDeskFeedItem[] {
  return (summary?.cards ?? []).slice(0, 3).map((card) => ({
    id: `risk-intel-${stableIdPart(card.id || card.title_ko)}`,
    category: 'risk',
    categoryLabel: CATEGORY_LABELS.risk,
    title: card.title_ko,
    whyItMatters: firstNonEmpty([
      card.summary_ko,
      card.rationale_ko,
      '리스크 인텔에서 확인이 필요한 항목입니다.',
    ]),
    affectedLabel: affectedRiskLabel(card),
    todayCheck: '관련 종목의 뉴스와 가격 반응을 먼저 확인하세요.',
    tone: riskTone(card),
    priority: riskPriority(card),
  }))
}

function buildEvidenceFeedItems(
  searchEvidence?: SearchEvidencePayload | null,
  qualityLoop?: QualityReliabilityLoopPayload | null,
): NewsDeskFeedItem[] {
  const priorityWarnings = countPriorityEvidenceWarnings(searchEvidence)
  const qualityWarnings = qualityLoop?.evidence_quality?.priority_not_refreshed_count ?? 0
  const providerErrors = searchEvidence?.run_summary?.provider_error_count ?? 0
  const warningCount = priorityWarnings > 0 ? Math.max(priorityWarnings, qualityWarnings) : 0

  if (priorityWarnings <= 0) {
    return []
  }

  return [
    {
      id: 'evidence-refresh-needed',
      category: 'evidence',
      categoryLabel: CATEGORY_LABELS.evidence,
      title: providerErrors > 0 ? '뉴스 데이터 확인 필요' : '일부 종목 근거 갱신 필요',
      whyItMatters: '오래된 뉴스나 부족한 근거는 오늘 판단에 영향을 줄 수 있습니다.',
      affectedLabel: warningCount > 0 ? `우선 점검 ${warningCount}건` : '근거 상태 확인',
      todayCheck: '우선 점검 종목의 최신 뉴스와 가격 반응을 확인하세요.',
      tone: providerErrors > 0 ? 'negative' : 'warning',
      priority: providerErrors > 0 ? 92 : 88,
    },
  ]
}

function buildMacroFeedItems(macroContext?: MacroContext | null): NewsDeskFeedItem[] {
  const event = macroContext?.macro_events?.[0] ?? macroContext?.upcoming_macro_events?.[0]
  const summary = firstNonEmpty([event?.summary_ko, event?.description])
  if (!event || !summary) return []
  const eventKey = firstNonEmpty([event.event_code, event.type, event.event_type, event.label, event.category])
  const title = firstNonEmpty([
    event.label,
    localizeMacroEventType(event.event_type),
    event.event_code,
    event.type,
    event.category,
    '시장 이벤트',
  ])

  return [
    {
      id: `macro-${stableIdPart(eventKey || title)}`,
      category: 'macro',
      categoryLabel: CATEGORY_LABELS.macro,
      title,
      whyItMatters: summary,
      affectedLabel:
        [...(event.affected_sectors ?? []), ...(event.affected_industries ?? [])]
          .filter(isNonEmpty)
          .slice(0, 3)
          .join(' / ') || '시장 전반',
      todayCheck: '금리 민감 섹터와 변동성 확대 여부를 확인하세요.',
      tone: event.severity === 'high' || event.impact === 'high' ? 'warning' : 'info',
      priority: event.severity === 'high' || event.impact === 'high' ? 82 : 66,
    },
  ]
}

function localizeMacroEventType(eventType?: string): string {
  if (!eventType) return ''
  return MACRO_EVENT_TYPE_LABELS[eventType] ?? eventType.replace(/_/g, ' ')
}

function buildActionFeedItems(feed?: ActionChangeFeedResult | null): NewsDeskFeedItem[] {
  return (feed?.entries ?? []).slice(0, 3).map((entry) => ({
    id: entry.id,
    category: 'ticker',
    categoryLabel: CATEGORY_LABELS.ticker,
    title: `${entry.ticker} ${entry.primaryLabel}`,
    whyItMatters: entry.summary,
    affectedLabel: `${entry.sector || '섹터 확인'} / ${entry.ticker}`,
    todayCheck: `${entry.ticker} 판단 변화의 근거를 확인하세요.`,
    tone: normalizeTone(entry.tone),
    priority: 72,
  }))
}

function buildTickerNewsItems(tickers: TickerAnalysisData[]): NewsDeskFeedItem[] {
  return tickers
    .flatMap((ticker) => ticker.key_news.slice(0, 1).map((news, newsIndex) => ({ ticker, news, newsIndex })))
    .slice(0, 3)
    .map(({ ticker, news, newsIndex }) => ({
      id: `ticker-news-${normalizeTicker(ticker.ticker)}-${newsIndex}`,
      category: 'news',
      categoryLabel: CATEGORY_LABELS.news,
      title: `${ticker.ticker} 주요 뉴스`,
      whyItMatters: news,
      affectedLabel: `${ticker.data_snapshot.Sector ?? '섹터 확인'} / ${ticker.ticker}`,
      todayCheck: `${ticker.ticker} 가격 반응과 리서치 근거를 함께 확인하세요.`,
      tone: normalizeTone(ticker.news_tone?.label),
      priority: ticker.decision?.action === 'buy' ? 64 : 58,
    }))
}

function buildMarketMoveFeedItems(marketMoves: NewsDeskMarketMoveItem[]): NewsDeskFeedItem[] {
  return marketMoves
    .filter((item) => (
      item.id.startsWith('real-asset-') &&
      item.directionLabel !== '안정' &&
      item.directionLabel !== '확인 필요'
    ))
    .map((item, index) => ({
      id: `market-move-${item.id}`,
      category: 'market' as const,
      categoryLabel: CATEGORY_LABELS.market,
      title: `${item.label} ${item.directionLabel}`,
      whyItMatters: `${item.label} 변화는 관련 섹터의 마진, 수요, 리스크 해석에 영향을 줄 수 있습니다.`,
      affectedLabel: item.id === 'real-asset-oil-wti' ? '에너지 / 산업재 / 소비재' : '시장 전반',
      todayCheck: `${item.label} 변화가 섹터와 종목 가격에 반영되는지 확인하세요.`,
      tone: item.tone,
      priority: 62 - index,
    }))
}

function buildImpacts(input: BuildDashboardNewsDeskInput): NewsDeskViewModel['impacts'] {
  const sectors = [
    ...(input.sectorMood?.focus ?? []).slice(0, 3).map((sector) => ({
      id: `sector-focus-${stableIdPart(sector.sector)}`,
      label: sector.sectorLabel || sector.sector,
      detail: sector.rationale || '시장 흐름과 정합성이 높은 섹터입니다.',
      tone: 'positive' as NewsDeskTone,
    })),
    ...(input.sectorMood?.watch ?? []).slice(0, 2).map((sector) => ({
      id: `sector-watch-${stableIdPart(sector.sector)}`,
      label: sector.sectorLabel || sector.sector,
      detail: sector.rationale || '오늘은 확인이 필요한 섹터입니다.',
      tone: 'warning' as NewsDeskTone,
    })),
  ]

  const tickers = (input.todayPriorityQueue?.items ?? []).slice(0, 4).map((item) => ({
    id: `impact-ticker-${normalizeTicker(item.ticker)}`,
    ticker: item.ticker,
    label: '오늘 우선 확인',
    detail: item.nextCheck,
    tone: normalizeTone(item.tone),
  }))

  return { sectors, tickers }
}

function buildMarketOverviewMove(entry: MarketOverviewEntry): NewsDeskMarketMoveItem | null {
  const label = firstNonEmpty([entry.label, entry.symbol])
  if (!label) return null
  const direction = directionFromChange(entry.change)

  return {
    id: `market-${stableIdPart(entry.symbol || label)}`,
    label,
    value: entry.price || 'N/A',
    change: entry.change || 'N/A',
    directionLabel: direction.label,
    tone: direction.tone,
  }
}

function buildMacroMoveItems(macroContext?: MacroContext | null): NewsDeskMarketMoveItem[] {
  if (!macroContext) return []

  return [
    metricToMove('real-asset-oil-wti', '유가 WTI', macroContext.oil_wti),
    metricToMove('real-asset-gold', '금', macroContext.gold),
    metricToMove('macro-dollar', '달러', macroContext.dxy),
    metricToMove('macro-us10y', '미국 10년 금리', macroContext.us10y),
    metricToMove('real-asset-copper', '구리', macroContext.copper),
  ].filter((item): item is NewsDeskMarketMoveItem => item !== null)
}

function metricToMove(
  id: string,
  label: string,
  metric?: { level?: string; price?: string; change?: string },
): NewsDeskMarketMoveItem | null {
  if (!metric) return null

  const value = firstNonEmpty([metric.level, metric.price]) || '확인 필요'
  const direction = directionFromChange(metric.change)

  return {
    id,
    label,
    value,
    change: metric.change ?? 'N/A',
    directionLabel: direction.label,
    tone: direction.tone,
  }
}

function directionFromChange(change?: string): {
  label: NewsDeskMarketMoveItem['directionLabel']
  tone: NewsDeskTone
} {
  if (!isNonEmpty(change)) return { label: '확인 필요', tone: 'neutral' }

  const value = numericValue(change)
  if (value === null) return { label: '혼조', tone: 'neutral' }
  if (value > 0) return { label: '상승', tone: 'positive' }
  if (value < 0) return { label: '하락', tone: 'negative' }
  return { label: '안정', tone: 'neutral' }
}

function breadthLabel(driver: string | undefined): string {
  if (!driver) return '확인 필요'
  if (includesAny(driver, ['mixed', '혼조'])) return '혼조'
  if (includesAny(driver, ['broad', '확산'])) return '확산'
  return '확인 필요'
}

function volatilityLabel(macroContext?: MacroContext | null): string {
  const regime = macroContext?.vix?.regime
  if (!regime) return '확인 필요'
  if (includesAny(regime, ['calm', 'low', '안정'])) return '안정'
  if (includesAny(regime, ['high', 'elevated', '높음'])) return '높음'
  return '보통'
}

function volatilityTone(macroContext?: MacroContext | null): NewsDeskTone {
  const label = volatilityLabel(macroContext)
  if (label === '높음') return 'warning'
  if (label === '안정') return 'positive'
  return 'neutral'
}

function toneFromRegime(regime?: MarketRegimeData['regime']): NewsDeskTone {
  if (regime === 'risk_on' || regime === 'reflation') return 'positive'
  if (regime === 'risk_off' || regime === 'defensive_bias') return 'warning'
  return 'neutral'
}

function normalizeTone(tone?: string): NewsDeskTone {
  if (tone === 'positive' || tone === 'bullish') return 'positive'
  if (tone === 'negative' || tone === 'bearish') return 'negative'
  if (tone === 'caution' || tone === 'warning') return 'warning'
  if (tone === 'info') return 'info'
  return 'neutral'
}

function riskTone(card: RiskIntelSummaryCard): NewsDeskTone {
  if (card.alert_level === 'alert') return 'negative'
  if (card.alert_level === 'warning') return 'warning'
  return 'info'
}

function riskPriority(card: RiskIntelSummaryCard): number {
  if (card.alert_level === 'alert') return 96
  if (card.alert_level === 'warning') return 84
  return 68
}

function affectedRiskLabel(card: RiskIntelSummaryCard): string {
  return [
    ...card.affected_sectors,
    ...card.affected_tickers.map((ticker) => ticker.ticker),
  ].filter(isNonEmpty).slice(0, 4).join(' / ') || '영향 범위 확인'
}

function hasEvidenceWarningState(searchEvidence?: SearchEvidencePayload | null): boolean {
  return countPriorityEvidenceWarnings(searchEvidence) > 0
}

function countPriorityEvidenceWarnings(searchEvidence?: SearchEvidencePayload | null): number {
  return Object.values(searchEvidence?.by_ticker ?? {}).filter((summary) => {
    const evidenceStatus = summary.evidence_status?.trim().toLowerCase()
    if (summary.priority_for_refresh !== true) return false

    return (
      evidenceStatus === 'not_refreshed' ||
      evidenceStatus === 'stale' ||
      evidenceStatus === 'missing' ||
      hasPriorityRefreshGapReason(summary.priority_refresh_reasons)
    )
  }).length
}

function hasPriorityRefreshGapReason(reasons: string[] | undefined): boolean {
  return (reasons ?? []).some((reason) => {
    const normalized = reason.trim().toLowerCase()
    return (
      normalized.includes('not_refreshed') ||
      normalized.includes('stale') ||
      normalized.includes('missing') ||
      normalized.includes('no_evidence') ||
      normalized.includes('provider_error') ||
      normalized.includes('zero_coverage')
    )
  })
}

function compareFeedItems(left: NewsDeskFeedItem, right: NewsDeskFeedItem): number {
  const priorityDiff = right.priority - left.priority
  if (priorityDiff !== 0) return priorityDiff

  const categoryDiff = CATEGORY_RANK[left.category] - CATEGORY_RANK[right.category]
  if (categoryDiff !== 0) return categoryDiff

  if (left.id < right.id) return -1
  if (left.id > right.id) return 1
  return 0
}

function resolveLimit(limit?: number): number {
  if (typeof limit !== 'number' || !Number.isFinite(limit)) return DEFAULT_FEED_LIMIT
  return Math.max(1, Math.floor(limit))
}

function numericValue(value: string): number | null {
  const normalized = value.replace(/,/g, '')
  const bpMatch = normalized.match(/([-+]?\d*\.?\d+)\s*bp/i)
  if (bpMatch) return Number.parseFloat(bpMatch[1] ?? '')

  const match = normalized.match(/[-+]?\d*\.?\d+/)
  if (!match) return null

  const parsed = Number.parseFloat(match[0] ?? '')
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeTicker(ticker: string): string {
  return ticker.trim().toUpperCase()
}

function stableIdPart(value?: string | null): string {
  return value?.trim().toLowerCase().replace(/[^a-z0-9가-힣]+/g, '-').replace(/^-+|-+$/g, '') || 'item'
}

function dedupeById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>()
  return items.filter((item) => {
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })
}

function firstNonEmpty(values: Array<string | undefined | null>): string {
  return values.find((value): value is string => isNonEmpty(value))?.trim() ?? ''
}

function isNonEmpty(value: string | undefined | null): value is string {
  return Boolean(value?.trim())
}

function includesAny(value: string, needles: string[]): boolean {
  const normalized = value.toLowerCase()
  return needles.some((needle) => normalized.includes(needle.toLowerCase()))
}

function isPartialData(day: DailyEntry, sectorMood?: SectorMoodResult | null): boolean {
  return (
    (day.market_overview?.length ?? 0) === 0 ||
    !day.market_regime ||
    day.tickers.length === 0 ||
    sectorMood?.hasSectorData === false
  )
}
