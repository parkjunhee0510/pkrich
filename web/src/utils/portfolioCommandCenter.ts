import type {
  PMEventExposureItem,
  PMSwapCandidate,
  PortfolioRisk,
  PortfolioRiskPosition,
  PortfolioSummaryData,
  TickerAnalysisData,
} from '../types'

export const PORTFOLIO_RISK_TERM_HELP = {
  hhi: 'HHI는 보유 비중을 제곱해 더한 집중도 지표입니다. 값이 높을수록 소수 종목에 포트폴리오가 몰려 있다는 뜻입니다.',
  beta: 'Beta는 포트폴리오가 시장 대비 얼마나 민감하게 움직이는지 보는 지표입니다. 1보다 크면 시장보다 변동성이 큰 편입니다.',
  var: 'VaR 95%는 평상시 변동성이 이어진다고 볼 때 하루 손실이 이 수준을 넘을 확률이 약 5%라는 의미의 추정치입니다.',
  correlation: '상관계수는 두 종목이 같은 방향으로 움직이는 정도입니다. 1에 가까울수록 분산 효과가 약해질 수 있습니다.',
  event: '이벤트 노출은 실적, 배당, 주요 일정처럼 단기 가격 변동을 키울 수 있는 보유 종목 일정을 뜻합니다.',
  swap: '교체 후보는 기존 보유 종목과 비교해 비중 조절 또는 대체 편입 검토가 필요한 후보입니다.',
  concentration: '집중도는 특정 종목이나 섹터 비중이 포트폴리오 전체에 미치는 영향입니다.',
  atr: 'ATR은 최근 가격 변동폭을 요약한 지표입니다. 값이 클수록 같은 비중에서도 손익 흔들림이 커질 수 있습니다.',
} as const

export type PortfolioCommandQueueType = 'event' | 'swap' | 'concentration' | 'correlation'
export type PortfolioCommandSeverity = 'high' | 'medium' | 'low'

export type PortfolioCommandQueueItem = {
  id: string
  type: PortfolioCommandQueueType
  ticker: string
  relatedTicker?: string
  title: string
  summary: string
  meta: string
  score: number
  severity: PortfolioCommandSeverity
  destination: string
  termHelp: string
  reasons: string[]
  reviewPoints: string[]
}

export type PortfolioRiskInsight = {
  id: string
  label: string
  value: string
  detail: string
  severity: PortfolioCommandSeverity
  termHelp: string
}

export type PortfolioCommandCenterData = {
  queue: PortfolioCommandQueueItem[]
  insights: PortfolioRiskInsight[]
  hasData: boolean
  counts: {
    events: number
    swaps: number
    insights: number
  }
}

type PortfolioCommandCenterInput = {
  portfolioSummary?: PortfolioSummaryData | null
  portfolioRisk?: PortfolioRisk | null
  pmEventExposure?: PMEventExposureItem[] | null
  pmSwapCandidates?: PMSwapCandidate[] | null
  tickerAnalyses?: TickerAnalysisData[] | null
}

const MAX_QUEUE_ITEMS = 5
const CONCENTRATION_WEIGHT_THRESHOLD = 25

const QUEUE_TYPE_ORDER: Record<PortfolioCommandQueueType, number> = {
  event: 0,
  swap: 1,
  concentration: 2,
  correlation: 3,
}

export function buildPortfolioCommandCenter(input: PortfolioCommandCenterInput): PortfolioCommandCenterData {
  const events = input.pmEventExposure ?? []
  const swaps = input.pmSwapCandidates ?? []
  const queue = buildActionQueue(input).slice(0, MAX_QUEUE_ITEMS)
  const insights = buildRiskInsights(input.portfolioRisk ?? null)
  const hasPortfolioPositions = (input.portfolioSummary?.positions.length ?? 0) > 0

  return {
    queue,
    insights,
    hasData: queue.length > 0 || insights.length > 0 || hasPortfolioPositions,
    counts: {
      events: events.length,
      swaps: swaps.length,
      insights: insights.length,
    },
  }
}

function buildActionQueue(input: PortfolioCommandCenterInput): PortfolioCommandQueueItem[] {
  const events = input.pmEventExposure ?? []
  const swaps = input.pmSwapCandidates ?? []
  const risk = input.portfolioRisk ?? null
  const riskPositions = risk?.positions_by_weight?.length
    ? risk.positions_by_weight
    : inferRiskPositions(input.portfolioSummary ?? null)
  const swapHeldTickers = new Set(swaps.map((item) => item.held_ticker).filter(Boolean))
  const items: PortfolioCommandQueueItem[] = [
    ...events.map((event) => eventToQueueItem(event, riskPositions)),
    ...swaps.map(swapToQueueItem),
    ...riskPositions
      .filter((position) => position.weight_pct >= CONCENTRATION_WEIGHT_THRESHOLD)
      .filter((position) => !swapHeldTickers.has(position.ticker))
      .map(concentrationToQueueItem),
    ...highCorrelationPairs(risk).map(correlationToQueueItem),
  ]

  return items.sort(compareQueueItems)
}

function eventToQueueItem(
  event: PMEventExposureItem,
  riskPositions: PortfolioRiskPosition[],
): PortfolioCommandQueueItem {
  const score = safeNumber(event.event_risk_score)
  const weight = riskPositions.find((position) => position.ticker === event.ticker)?.weight_pct
  const metaParts = [formatDaysUntil(event.days_until)]

  if (weight != null) {
    metaParts.push(`${formatPct(weight, 1)} 비중`)
  }

  return {
    id: `event:${event.ticker}`,
    type: 'event',
    ticker: event.ticker,
    title: event.event_label || '이벤트 노출',
    summary: event.summary || '다가오는 일정 전후로 포지션 점검이 필요합니다.',
    meta: metaParts.join(' · '),
    score,
    severity: eventSeverity(score, event.days_until),
    destination: `/ticker/${event.ticker}`,
    termHelp: PORTFOLIO_RISK_TERM_HELP.event,
    reasons: event.reasons ?? [],
    reviewPoints: event.review_points ?? [],
  }
}

function swapToQueueItem(item: PMSwapCandidate): PortfolioCommandQueueItem {
  const score = safeNumber(item.swap_candidate_score)

  return {
    id: `swap:${item.held_ticker}:${item.candidate_ticker}`,
    type: 'swap',
    ticker: item.held_ticker,
    relatedTicker: item.candidate_ticker,
    title: `${item.held_ticker} -> ${item.candidate_ticker} 교체 검토`,
    summary: item.summary || '보유 종목과 대체 후보의 역할을 비교할 필요가 있습니다.',
    meta: compactParts([item.overlap_context, `점수 ${formatNumber(score, 0)}`]),
    score,
    severity: scoreSeverity(score, 80, 60),
    destination: `/ticker/${item.held_ticker}`,
    termHelp: PORTFOLIO_RISK_TERM_HELP.swap,
    reasons: item.reasons ?? [],
    reviewPoints: item.review_points ?? [],
  }
}

function concentrationToQueueItem(position: PortfolioRiskPosition): PortfolioCommandQueueItem {
  const weight = safeNumber(position.weight_pct)
  const meta = compactParts([
    position.sector ?? 'Sector N/A',
    position.atr_risk_usd ? `ATR ${formatCurrency(position.atr_risk_usd)}` : '',
  ])

  return {
    id: `concentration:${position.ticker}`,
    type: 'concentration',
    ticker: position.ticker,
    title: `${position.ticker} 비중 점검`,
    summary: `${position.ticker} 비중이 ${formatPct(weight, 1)}로 포트폴리오 손익에 크게 반영될 수 있습니다.`,
    meta,
    score: weight,
    severity: weight >= 35 ? 'high' : 'medium',
    destination: `/ticker/${position.ticker}`,
    termHelp: PORTFOLIO_RISK_TERM_HELP.concentration,
    reasons: ['단일 종목 비중이 높습니다.'],
    reviewPoints: ['유지, 일부 축소, 헤지 필요 여부를 확인합니다.'],
  }
}

function correlationToQueueItem(pair: Required<PortfolioRisk>['correlation_pairs'][number]): PortfolioCommandQueueItem {
  const correlation = Math.abs(parseCorrelation(pair.correlation))
  const score = correlation * 100

  return {
    id: `correlation:${pair.ticker_1}:${pair.ticker_2}`,
    type: 'correlation',
    ticker: pair.ticker_1,
    relatedTicker: pair.ticker_2,
    title: `${pair.ticker_1}/${pair.ticker_2} 고상관`,
    summary: pair.warning || '두 종목이 같은 방향으로 움직일 가능성이 커 분산 효과가 제한될 수 있습니다.',
    meta: `${pair.ticker_1}/${pair.ticker_2} · ${formatNumber(correlation, 2)}`,
    score,
    severity: correlation >= 0.8 ? 'high' : 'medium',
    destination: `/ticker/${pair.ticker_1}`,
    termHelp: PORTFOLIO_RISK_TERM_HELP.correlation,
    reasons: [pair.warning].filter(Boolean),
    reviewPoints: ['같은 리스크 요인에 동시에 노출되어 있는지 확인합니다.'],
  }
}

function buildRiskInsights(risk: PortfolioRisk | null): PortfolioRiskInsight[] {
  if (!risk) {
    return []
  }

  const insights: PortfolioRiskInsight[] = []

  if (risk.hhi != null) {
    insights.push({
      id: 'hhi',
      label: 'HHI 집중도',
      value: formatNumber(risk.hhi, 0),
      detail: risk.concentration_warning || hhiDetail(risk.hhi),
      severity: hhiSeverity(risk.hhi),
      termHelp: PORTFOLIO_RISK_TERM_HELP.hhi,
    })
  }

  if (risk.portfolio_beta != null) {
    insights.push({
      id: 'beta',
      label: 'Portfolio Beta',
      value: formatNumber(risk.portfolio_beta, 2),
      detail: betaDetail(risk.portfolio_beta),
      severity: Math.abs(risk.portfolio_beta) >= 1.25 ? 'high' : 'medium',
      termHelp: PORTFOLIO_RISK_TERM_HELP.beta,
    })
  }

  if (risk.var_95 != null) {
    insights.push({
      id: 'var',
      label: '1일 VaR 95%',
      value: `${formatNumber(risk.var_95, 1)}%`,
      detail: `정상적인 변동성 가정에서 하루 손실 기준점은 약 ${formatNumber(risk.var_95, 1)}%입니다.`,
      severity: risk.var_95 >= 3 ? 'high' : 'medium',
      termHelp: PORTFOLIO_RISK_TERM_HELP.var,
    })
  }

  const topSector = topSectorExposure(risk)
  if (topSector) {
    insights.push({
      id: 'sector',
      label: '최대 섹터',
      value: `${formatPct(topSector.weight, 1)}`,
      detail: `${topSector.sector} 섹터가 가장 큰 비중을 차지합니다.`,
      severity: topSector.weight >= 60 ? 'high' : 'medium',
      termHelp: PORTFOLIO_RISK_TERM_HELP.concentration,
    })
  }

  const topCorrelation = topCorrelationPair(risk)
  if (topCorrelation) {
    const correlation = Math.abs(parseCorrelation(topCorrelation.correlation))
    insights.push({
      id: 'correlation',
      label: '상관 리스크',
      value: formatNumber(correlation, 2),
      detail: `${topCorrelation.ticker_1}/${topCorrelation.ticker_2}: ${topCorrelation.warning}`,
      severity: correlation >= 0.8 ? 'high' : 'medium',
      termHelp: PORTFOLIO_RISK_TERM_HELP.correlation,
    })
  }

  return insights
}

function highCorrelationPairs(risk: PortfolioRisk | null): Required<PortfolioRisk>['correlation_pairs'] {
  return (risk?.correlation_pairs ?? [])
    .filter((pair) => Math.abs(parseCorrelation(pair.correlation)) >= 0.75)
    .sort((left, right) => Math.abs(parseCorrelation(right.correlation)) - Math.abs(parseCorrelation(left.correlation)))
}

function topCorrelationPair(risk: PortfolioRisk): Required<PortfolioRisk>['correlation_pairs'][number] | null {
  const pairs = highCorrelationPairs(risk)
  return pairs.length > 0 ? pairs[0] : null
}

function topSectorExposure(risk: PortfolioRisk): { sector: string; weight: number } | null {
  const entries = Object.entries(risk.sector_exposure ?? {}).sort(([, left], [, right]) => right - left)
  if (entries.length === 0) {
    return null
  }

  const [sector, weight] = entries[0]
  return { sector, weight }
}

function inferRiskPositions(summary: PortfolioSummaryData | null): PortfolioRiskPosition[] {
  const totalMarketValue =
    summary?.total_market_value || (summary?.positions ?? []).reduce((total, position) => total + position.market_value, 0)

  return (summary?.positions ?? []).map((position) => ({
    ticker: position.ticker,
    weight_pct: totalMarketValue > 0 ? (position.market_value / totalMarketValue) * 100 : 0,
    market_value: position.market_value,
    atr_risk_usd: 0,
  }))
}

function compareQueueItems(left: PortfolioCommandQueueItem, right: PortfolioCommandQueueItem): number {
  const typeDifference = QUEUE_TYPE_ORDER[left.type] - QUEUE_TYPE_ORDER[right.type]
  if (typeDifference !== 0) {
    return typeDifference
  }

  const scoreDifference = right.score - left.score
  if (scoreDifference !== 0) {
    return scoreDifference
  }

  return left.id.localeCompare(right.id)
}

function eventSeverity(score: number, daysUntil: number): PortfolioCommandSeverity {
  if (score >= 80 || (Number.isFinite(daysUntil) && daysUntil <= 3)) {
    return 'high'
  }
  if (score >= 55 || (Number.isFinite(daysUntil) && daysUntil <= 14)) {
    return 'medium'
  }
  return 'low'
}

function scoreSeverity(score: number, high: number, medium: number): PortfolioCommandSeverity {
  if (score >= high) {
    return 'high'
  }
  if (score >= medium) {
    return 'medium'
  }
  return 'low'
}

function hhiSeverity(value: number): PortfolioCommandSeverity {
  if (value >= 2500) {
    return 'high'
  }
  if (value >= 1800) {
    return 'medium'
  }
  return 'low'
}

function hhiDetail(value: number): string {
  if (value >= 2500) {
    return '소수 종목 비중이 커 집중 리스크가 높은 구간입니다.'
  }
  if (value >= 1800) {
    return '분산은 되어 있지만 일부 종목 영향이 커질 수 있는 구간입니다.'
  }
  return '종목별 비중이 비교적 분산된 구간입니다.'
}

function betaDetail(value: number): string {
  if (value > 1.1) {
    return '시장 상승과 하락에 더 크게 반응할 수 있는 포트폴리오입니다.'
  }
  if (value < 0.9) {
    return '시장보다 변동성이 낮은 방어적 성격이 강한 편입니다.'
  }
  return '시장과 비슷한 민감도로 움직이는 구간입니다.'
}

function formatDaysUntil(value: number): string {
  if (!Number.isFinite(value) || value < 0) {
    return '일정 확인 필요'
  }
  if (value === 0) {
    return 'D-Day'
  }
  if (value <= 30) {
    return `D-${value}`
  }
  return '추후 일정'
}

function formatCurrency(value: number): string {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function formatPct(value: number, digits = 1): string {
  return `${formatNumber(value, digits)}%`
}

function formatNumber(value: number, digits: number): string {
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

function safeNumber(value: number | null | undefined): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function parseCorrelation(value: string): number {
  const parsed = Number.parseFloat(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function compactParts(parts: string[]): string {
  return parts.filter(Boolean).join(' · ')
}
