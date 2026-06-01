import type {
  DailyEntry,
  QualityReliabilityLoopPayload,
  RiskIntelAlertLevel,
  RiskIntelSummaryCard,
  RiskIntelSummaryPayload,
  SearchEvidencePayload,
  SearchEvidenceTickerSummary,
  TickerAnalysisData,
  TickerDecisionData,
} from '../types'

export type TodayPriorityLevel = 'none' | 'low' | 'medium' | 'high' | 'unknown'
export type TodayEvidenceStatus = 'covered' | 'not_refreshed' | 'stale' | 'missing' | 'unknown'
export type TodayPriorityTone = 'positive' | 'negative' | 'caution' | 'neutral' | 'info'

export interface TodayPriorityQueueItem {
  id: string
  ticker: string
  name: string
  officialAction: string
  priorityScore: number
  priorityLabel: string
  tone: TodayPriorityTone
  riskLevel: TodayPriorityLevel
  riskLabel: string
  opportunityLevel: TodayPriorityLevel
  opportunityLabel: string
  evidenceStatus: TodayEvidenceStatus
  evidenceLabel: string
  reasons: string[]
  nextCheck: string
  destination: string
}

export interface TodayPriorityQueueResult {
  items: TodayPriorityQueueItem[]
  asOf: string
  evidenceHealthLabel: string
  qualityWarnings: string[]
  emptyLabel: string
}

export interface BuildTodayPriorityQueueInput {
  day: DailyEntry
  previousDay?: DailyEntry | null
  searchEvidence?: SearchEvidencePayload | null
  riskIntelSummary?: RiskIntelSummaryPayload | null
  qualityLoop?: QualityReliabilityLoopPayload | null
  limit?: number
}

interface ScoredQueueItem {
  item: TodayPriorityQueueItem
  index: number
}

interface RiskAssessment {
  score: number
  level: TodayPriorityLevel
  label: string
  reasons: string[]
}

interface OpportunityAssessment {
  score: number
  level: TodayPriorityLevel
  label: string
  reasons: string[]
}

interface EvidenceAssessment {
  score: number
  status: TodayEvidenceStatus
  label: string
  reasons: string[]
}

const DEFAULT_LIMIT = 8
const EMPTY_LABEL = '오늘 별도 우선 점검 종목 없음'

const ACTION_LABELS: Record<TickerDecisionData['action'], string> = {
  buy: 'BUY',
  watch: 'WATCH',
  avoid: 'AVOID',
}

const RISK_BY_ALERT_LEVEL: Record<RiskIntelAlertLevel, RiskAssessment> = {
  alert: {
    score: 35,
    level: 'high',
    label: 'Risk high',
    reasons: [],
  },
  warning: {
    score: 24,
    level: 'medium',
    label: 'Risk medium',
    reasons: [],
  },
  observation: {
    score: 12,
    level: 'low',
    label: 'Risk watch',
    reasons: [],
  },
}

const RISK_LEVEL_RANK: Record<TodayPriorityLevel, number> = {
  unknown: -1,
  none: 0,
  low: 1,
  medium: 2,
  high: 3,
}

export function buildTodayPriorityQueue(input: BuildTodayPriorityQueueInput): TodayPriorityQueueResult {
  const limit = resolveLimit(input.limit)
  const previousByTicker = tickerMap(input.previousDay?.tickers ?? [])
  const evidenceByTicker = searchEvidenceMap(input.searchEvidence)

  const items = input.day.tickers
    .map((ticker, index) => ({
      item: buildQueueItem(ticker, index, previousByTicker, evidenceByTicker, input),
      index,
    }))
    .filter((row): row is ScoredQueueItem => row.item.priorityScore > 0)
    .sort(compareQueueItems)
    .slice(0, limit)
    .map((row) => row.item)

  return {
    items,
    asOf: input.day.date,
    evidenceHealthLabel: evidenceHealthLabel(input.searchEvidence, input.qualityLoop),
    qualityWarnings: uniqueStrings(input.qualityLoop?.warnings ?? []),
    emptyLabel: EMPTY_LABEL,
  }
}

function buildQueueItem(
  tickerData: TickerAnalysisData,
  _index: number,
  previousByTicker: Map<string, TickerAnalysisData>,
  evidenceByTicker: Map<string, SearchEvidenceTickerSummary> | null,
  input: BuildTodayPriorityQueueInput,
): TodayPriorityQueueItem {
  const ticker = normalizeTicker(tickerData.ticker)
  const risk = assessRisk(ticker, input.riskIntelSummary)
  const opportunity = assessOpportunity(tickerData)
  const evidence = assessEvidence(ticker, evidenceByTicker, input.searchEvidence)
  const actionContext = assessActionContext(tickerData, previousByTicker.get(ticker))
  const reasons = uniqueStrings([
    ...risk.reasons,
    ...opportunity.reasons,
    ...evidence.reasons,
    ...actionContext.reasons,
  ]).slice(0, 4)
  const priorityScore = risk.score + opportunity.score + evidence.score + actionContext.score

  return {
    id: `today-priority-${ticker}`,
    ticker,
    name: tickerData.name,
    officialAction: officialActionLabel(tickerData.decision?.action),
    priorityScore,
    priorityLabel: priorityLabel(risk.level, opportunity.level, evidence.status),
    tone: priorityTone(risk.level, opportunity.level, evidence.status),
    riskLevel: risk.level,
    riskLabel: risk.label,
    opportunityLevel: opportunity.level,
    opportunityLabel: opportunity.label,
    evidenceStatus: evidence.status,
    evidenceLabel: evidence.label,
    reasons,
    nextCheck: nextCheck(risk.level, opportunity.level, evidence.status),
    destination: `/ticker/${ticker}`,
  }
}

function assessRisk(
  ticker: string,
  riskIntelSummary: RiskIntelSummaryPayload | null | undefined,
): RiskAssessment {
  if (!riskIntelSummary) {
    return {
      score: 0,
      level: 'unknown',
      label: 'Risk unknown',
      reasons: [],
    }
  }

  const matchingCards = riskIntelSummary.cards.filter((card) => cardAffectsTicker(card, ticker))
  if (matchingCards.length === 0) {
    return {
      score: 0,
      level: 'none',
      label: 'Risk none',
      reasons: [],
    }
  }

  const highestLevel = matchingCards.reduce<RiskIntelAlertLevel>(
    (current, card) =>
      RISK_LEVEL_RANK[RISK_BY_ALERT_LEVEL[card.alert_level].level] >
      RISK_LEVEL_RANK[RISK_BY_ALERT_LEVEL[current].level]
        ? card.alert_level
        : current,
    matchingCards[0].alert_level,
  )
  const base = RISK_BY_ALERT_LEVEL[highestLevel]

  return {
    ...base,
    reasons: matchingCards
      .map(riskReason)
      .filter((reason): reason is string => Boolean(reason))
      .slice(0, 2),
  }
}

function assessOpportunity(tickerData: TickerAnalysisData): OpportunityAssessment {
  const reasons: string[] = []
  let score = 0
  const action = tickerData.decision?.action
  const conviction = numericValue(tickerData.decision?.conviction)

  if (action === 'buy' && (conviction ?? 0) >= 70) {
    score += 30
    reasons.push('BUY with high conviction')
  } else if (action === 'buy') {
    score += 22
    reasons.push('BUY action under review')
  }

  if (tickerData.news_tone?.label === 'bullish') {
    score += 8
    reasons.push('Bullish news tone')
  }

  if ((numericValue(tickerData.price_action?.relative_volume) ?? 0) >= 1.2) {
    score += 6
    reasons.push('Relative volume above 1.2')
  }

  const spyRelativeStrength = numericValue(tickerData.price_action?.rs_vs_spy) ?? 0
  const sectorRelativeStrength = numericValue(tickerData.price_action?.rs_vs_sector_etf) ?? 0
  if (spyRelativeStrength > 0 || sectorRelativeStrength > 0) {
    score += 6
    reasons.push('Positive relative strength')
  }

  const level = opportunityLevel(score)
  return {
    score,
    level,
    label: opportunityLabel(level),
    reasons,
  }
}

function assessEvidence(
  ticker: string,
  evidenceByTicker: Map<string, SearchEvidenceTickerSummary> | null,
  searchEvidence: SearchEvidencePayload | null | undefined,
): EvidenceAssessment {
  if (!searchEvidence || !evidenceByTicker) {
    return {
      score: 0,
      status: 'unknown',
      label: 'Evidence unknown',
      reasons: [],
    }
  }

  const evidence = evidenceByTicker.get(ticker)
  if (!evidence) {
    return {
      score: 10,
      status: 'missing',
      label: 'Evidence missing',
      reasons: ['Search evidence coverage is missing'],
    }
  }

  const priorityRefreshReasons = normalizeReasonCodes(evidence.priority_refresh_reasons ?? [])
  if (priorityRefreshReasons.includes('not_refreshed')) {
    return {
      score: 20,
      status: 'not_refreshed',
      label: 'Evidence refresh needed',
      reasons: ['Priority evidence was not refreshed'],
    }
  }

  const cacheAgeHours = numericValue(evidence.cache_age_hours)
  const cacheTtlHours = numericValue(searchEvidence.run_summary?.cache_ttl_hours)
  if (
    cacheAgeHours !== null &&
    cacheTtlHours !== null &&
    cacheTtlHours >= 0 &&
    cacheAgeHours > cacheTtlHours
  ) {
    return {
      score: 12,
      status: 'stale',
      label: 'Evidence stale',
      reasons: ['Search evidence cache is stale'],
    }
  }

  const evidenceStatus = normalizeStatus(evidence.evidence_status)
  if ((numericValue(evidence.evidence_count) ?? 0) > 0 || evidenceStatus === 'covered') {
    return {
      score: 0,
      status: 'covered',
      label: 'Evidence covered',
      reasons: [],
    }
  }

  if (evidenceStatus === 'no_evidence' || evidenceStatus === 'provider_error') {
    return {
      score: 16,
      status: 'missing',
      label: 'Evidence missing',
      reasons: ['Search evidence coverage is missing'],
    }
  }

  return {
    score: 0,
    status: 'unknown',
    label: 'Evidence unknown',
    reasons: [],
  }
}

function assessActionContext(
  tickerData: TickerAnalysisData,
  previousTicker: TickerAnalysisData | undefined,
): { score: number; reasons: string[] } {
  const action = tickerData.decision?.action
  const reasons: string[] = []
  let score = 0

  if (action === 'buy' || action === 'avoid') {
    score += 8
    reasons.push(`${ACTION_LABELS[action]} action needs human review`)
  }

  const previousAction = previousTicker?.decision?.action
  if (previousAction && action && previousAction !== action) {
    score += 12
    reasons.push(`Action changed from ${ACTION_LABELS[previousAction]} to ${ACTION_LABELS[action]}`)
  }

  return { score, reasons }
}

function compareQueueItems(left: ScoredQueueItem, right: ScoredQueueItem): number {
  const scoreDiff = right.item.priorityScore - left.item.priorityScore
  if (scoreDiff !== 0) return scoreDiff
  return left.index - right.index
}

function cardAffectsTicker(card: RiskIntelSummaryCard, ticker: string): boolean {
  return card.affected_tickers.some((affectedTicker) => normalizeTicker(affectedTicker.ticker) === ticker)
}

function riskReason(card: RiskIntelSummaryCard): string {
  return firstNonEmpty([
    card.title_ko,
    card.summary_ko,
    'Risk intelligence alert',
  ])
}

function opportunityLevel(score: number): TodayPriorityLevel {
  if (score >= 30) return 'high'
  if (score >= 16) return 'medium'
  if (score > 0) return 'low'
  return 'none'
}

function opportunityLabel(level: TodayPriorityLevel): string {
  if (level === 'high') return 'Opportunity high'
  if (level === 'medium') return 'Opportunity medium'
  if (level === 'low') return 'Opportunity watch'
  return 'Opportunity none'
}

function priorityLabel(
  riskLevel: TodayPriorityLevel,
  opportunityLevelValue: TodayPriorityLevel,
  evidenceStatus: TodayEvidenceStatus,
): string {
  const hasRisk = isMediumOrHigh(riskLevel)
  const hasOpportunity = isMediumOrHigh(opportunityLevelValue)

  if (hasRisk && hasOpportunity) return 'Risk and opportunity review'
  if (hasRisk) return 'Risk-led review'
  if (hasOpportunity) return 'Opportunity-led review'
  if (isEvidenceGap(evidenceStatus)) return 'Evidence review'
  return 'Review'
}

function priorityTone(
  riskLevel: TodayPriorityLevel,
  opportunityLevelValue: TodayPriorityLevel,
  evidenceStatus: TodayEvidenceStatus,
): TodayPriorityTone {
  if (riskLevel === 'high') return 'negative'
  if (opportunityLevelValue === 'high') return 'positive'
  if (isEvidenceGap(evidenceStatus)) return 'caution'
  if (riskLevel === 'medium' || opportunityLevelValue === 'medium') return 'info'
  return 'neutral'
}

function nextCheck(
  riskLevel: TodayPriorityLevel,
  opportunityLevelValue: TodayPriorityLevel,
  evidenceStatus: TodayEvidenceStatus,
): string {
  if (riskLevel === 'high') return '리스크 경로와 보유 영향부터 확인하세요.'
  if (opportunityLevelValue === 'high' && evidenceStatus !== 'covered') {
    return '기회는 강하지만 근거 갱신을 먼저 확인하세요.'
  }
  if (opportunityLevelValue === 'high') return '기회 근거와 진입 조건을 확인하세요.'
  if (isEvidenceGap(evidenceStatus)) return '근거 부족이 판단을 흔드는지 확인하세요.'
  return '핵심 논점과 공식 판단을 확인하세요.'
}

function evidenceHealthLabel(
  searchEvidence: SearchEvidencePayload | null | undefined,
  qualityLoop: QualityReliabilityLoopPayload | null | undefined,
): string {
  if (!searchEvidence && !qualityLoop) return '근거 상태 없음'

  const coverageRatio = numericValue(qualityLoop?.evidence_quality?.coverage_ratio)
  if (coverageRatio !== null) {
    return `Evidence coverage ${(coverageRatio * 100).toFixed(0)}%`
  }

  const evidenceStatus = qualityLoop?.summary?.evidence_status?.trim()
  if (evidenceStatus) return `Evidence ${evidenceStatus}`

  return 'Evidence loaded'
}

function searchEvidenceMap(
  searchEvidence: SearchEvidencePayload | null | undefined,
): Map<string, SearchEvidenceTickerSummary> | null {
  if (!searchEvidence) return null

  const byTicker = new Map<string, SearchEvidenceTickerSummary>()
  for (const [ticker, evidence] of Object.entries(searchEvidence.by_ticker ?? {})) {
    byTicker.set(normalizeTicker(ticker), evidence)
  }
  return byTicker
}

function tickerMap(tickers: TickerAnalysisData[]): Map<string, TickerAnalysisData> {
  return new Map(tickers.map((ticker) => [normalizeTicker(ticker.ticker), ticker]))
}

function isMediumOrHigh(level: TodayPriorityLevel): boolean {
  return level === 'medium' || level === 'high'
}

function isEvidenceGap(status: TodayEvidenceStatus): boolean {
  return status === 'not_refreshed' || status === 'missing' || status === 'stale'
}

function officialActionLabel(action: TickerDecisionData['action'] | undefined): string {
  return action ? ACTION_LABELS[action] : 'N/A'
}

function resolveLimit(limit: number | undefined): number {
  if (limit === undefined) return DEFAULT_LIMIT
  return Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : DEFAULT_LIMIT
}

function numericValue(value: unknown): number | null {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null
  }

  if (typeof value !== 'string') return null

  const trimmed = value.trim()
  if (!trimmed || trimmed.toLowerCase() === 'n/a') return null

  const parsed = Number.parseFloat(trimmed.replace(/,/g, ''))
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeTicker(ticker: string): string {
  return ticker.trim().toUpperCase()
}

function normalizeStatus(status: string | undefined): string {
  return status?.trim().toLowerCase() ?? ''
}

function normalizeReasonCodes(reasons: string[]): string[] {
  return reasons.map((reason) => reason.trim().toLowerCase()).filter(Boolean)
}

function uniqueStrings(values: string[]): string[] {
  const seen = new Set<string>()
  const unique: string[] = []

  for (const value of values) {
    const trimmed = value.trim()
    if (!trimmed || seen.has(trimmed)) continue
    seen.add(trimmed)
    unique.push(trimmed)
  }

  return unique
}

function firstNonEmpty(values: Array<string | undefined>): string {
  for (const value of values) {
    const trimmed = value?.trim()
    if (trimmed) return trimmed
  }

  return 'Risk intelligence alert'
}
