import type { MacroContext, MacroEvent, MarketRegimeData, TickerAnalysisData } from '../types'

export type SectorMoodClassification = 'focus' | 'neutral' | 'watch'
export type SectorFitLabel = '정합 높음' | '중립' | '정합 낮음' | '확인 필요'

export interface SectorTickerRef {
  ticker: string
  action?: 'buy' | 'watch' | 'avoid'
  conviction: number | null
  dailyChange: number | null
}

export interface SectorMoodInsight {
  sector: string
  sectorLabel: string
  tickerCount: number
  classification: SectorMoodClassification
  fitLabel: SectorFitLabel
  averageDailyChange: number | null
  positiveTickerRatio: number | null
  topGainer: SectorTickerRef | null
  topLoser: SectorTickerRef | null
  representativeTickers: SectorTickerRef[]
  priceFlowScore: number
  regimeFitScore: number
  tickerSignalScore: number
  eventExposureScore: number
  score: number
  macroEvidence: MacroEvent[]
  rationale: string
}

export interface SectorMoodResult {
  insights: SectorMoodInsight[]
  focus: SectorMoodInsight[]
  watch: SectorMoodInsight[]
  neutral: SectorMoodInsight[]
  hasSectorData: boolean
  emptyReason?: string
}

export interface DeriveSectorMoodInput {
  tickers: TickerAnalysisData[]
  marketRegime?: MarketRegimeData | null
  regime?: MarketRegimeData | null
  macroContext?: MacroContext | null
}

const SECTOR_LABELS: Record<string, string> = {
  Technology: '기술',
  Semiconductors: '반도체',
  Healthcare: '헬스케어',
  Financials: '금융',
  Financial: '금융',
  'Financial Services': '금융',
  Energy: '에너지',
  'Consumer Discretionary': '경기소비재',
  'Consumer Cyclical': '경기소비재',
  'Consumer Staples': '필수소비재',
  'Consumer Defensive': '필수소비재',
  Industrials: '산업재',
  Communication: '커뮤니케이션',
  'Communication Services': '커뮤니케이션',
  Utilities: '유틸리티',
  'Real Estate': '부동산',
  Materials: '소재',
  'Basic Materials': '소재',
  Other: '기타',
}

const SECTOR_MATCH_ALIASES: Record<string, string> = {
  'consumer staples': 'consumer-staples',
  'consumer defensive': 'consumer-staples',
  필수소비재: 'consumer-staples',
  'consumer discretionary': 'consumer-discretionary',
  'consumer cyclical': 'consumer-discretionary',
  경기소비재: 'consumer-discretionary',
  financials: 'financials',
  financial: 'financials',
  'financial services': 'financials',
  금융: 'financials',
  communication: 'communication-services',
  'communication services': 'communication-services',
  커뮤니케이션: 'communication-services',
  materials: 'materials',
  'basic materials': 'materials',
  소재: 'materials',
}

const FACTOR_KEYS = ['macro_regime', 'regime_adjustment', 'macro_event'] as const
type FactorScoreKey = typeof FACTOR_KEYS[number]

const FACTOR_NORMALIZATION_BOUNDS: Record<FactorScoreKey, { negative: number; positive: number }> = {
  macro_regime: { negative: 6, positive: 8 },
  regime_adjustment: { negative: 15, positive: 15 },
  macro_event: { negative: 8, positive: 6 },
}

const BEARISH_EVENT_PHRASES = [
  '위험 선호 약화',
  '위험 선호 둔화',
  '위험 선호 악화',
  'risk appetite weak',
  'risk appetite weaken',
  'risk appetite deteriorat',
  'risk-on fading',
  'risk-on fade',
  'support broke',
  'support break',
]
const POSITIVE_EVENT_PHRASES = [
  '위험 선호',
  'risk-on',
  'risk appetite',
  '완화',
  '개선',
  '강세',
  'dovish',
  'positive',
  'tailwind',
  'support',
]
const NEGATIVE_EVENT_PHRASES = [
  '부담',
  '압박',
  '위험 부담',
  '위험 압박',
  '위험 악화',
  '위험 회피',
  '악화',
  'hawkish',
  'negative',
  'headwind',
  'risk-off',
  'risk aversion',
  'risk avoidance',
  'risk pressure',
  'risk burden',
  'volatility',
]

export function deriveSectorMoodInsights(input: DeriveSectorMoodInput): SectorMoodResult {
  const marketRegime = input.marketRegime ?? input.regime

  if (input.tickers.length === 0) {
    return {
      insights: [],
      focus: [],
      watch: [],
      neutral: [],
      hasSectorData: false,
      emptyReason: '섹터 데이터 부족',
    }
  }

  const grouped = groupBySector(input.tickers)
  const insights = Array.from(grouped.entries())
    .map(([sector, tickers]) => buildSectorInsight(sector, tickers, marketRegime, input.macroContext))
    .sort((left, right) => right.score - left.score)

  const focus = insights
    .filter((insight) => isFocusCandidate(insight))
    .slice(0, 3)

  const focusSectors = new Set(focus.map((insight) => insight.sector))
  const watch = insights
    .filter((insight) => !focusSectors.has(insight.sector) && isWatchCandidate(insight))
    .sort((left, right) => left.score - right.score)
    .slice(0, 3)

  const watchSectors = new Set(watch.map((insight) => insight.sector))
  const classified = insights.map((insight) => {
    if (focusSectors.has(insight.sector)) return { ...insight, classification: 'focus' as const }
    if (watchSectors.has(insight.sector)) return { ...insight, classification: 'watch' as const }
    return { ...insight, classification: 'neutral' as const }
  })
  const classifiedBySector = new Map(classified.map((insight) => [insight.sector, insight]))

  return {
    insights: classified,
    focus: focus.map((insight) => classifiedBySector.get(insight.sector)).filter((insight): insight is SectorMoodInsight => Boolean(insight)),
    watch: watch.map((insight) => classifiedBySector.get(insight.sector)).filter((insight): insight is SectorMoodInsight => Boolean(insight)),
    neutral: classified.filter((insight) => insight.classification === 'neutral'),
    hasSectorData: true,
  }
}

export function buildMarketMoodSummary(
  regime: MarketRegimeData | null | undefined,
  sectorMood: SectorMoodResult,
): string {
  const regimeLabel = regime?.regime ?? '시장 분위기 정보 없음'
  if (!sectorMood.hasSectorData || (sectorMood.focus.length === 0 && sectorMood.watch.length === 0)) {
    return `${regimeLabel} · 매크로와 섹터 흐름`
  }

  return `${regimeLabel} · 주목 ${sectorMood.focus.length}개 / 주의 ${sectorMood.watch.length}개 · 매크로와 섹터 흐름`
}

export function getSectorLabel(sector: string): string {
  return SECTOR_LABELS[sector] ?? sector
}

export function formatSectorPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return 'N/A'
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

function groupBySector(tickers: TickerAnalysisData[]): Map<string, TickerAnalysisData[]> {
  const grouped = new Map<string, TickerAnalysisData[]>()
  for (const ticker of tickers) {
    const sector = ticker.data_snapshot['Sector']?.trim() || 'Other'
    grouped.set(sector, [...(grouped.get(sector) ?? []), ticker])
  }
  return grouped
}

function buildSectorInsight(
  sector: string,
  tickers: TickerAnalysisData[],
  regime: MarketRegimeData | null | undefined,
  macroContext: MacroContext | null | undefined,
): SectorMoodInsight {
  const refs = tickers.map(toTickerRef)
  const parsedChanges = refs
    .map((ref) => ref.dailyChange)
    .filter((value): value is number => value !== null)
  const averageDailyChange = average(parsedChanges)
  const positiveTickerRatio = parsedChanges.length === 0
    ? null
    : parsedChanges.filter((value) => value > 0).length / parsedChanges.length
  const representativeTickers = [...refs].sort(compareTickerRefs).slice(0, 4)
  const priceFlowScore = computePriceFlowScore(averageDailyChange, positiveTickerRatio)
  const regimeFitScore = computeRegimeFitScore(tickers)
  const tickerSignalScore = computeTickerSignalScore(refs)
  const macroEvidence = findMacroEvidence(sector, macroContext)
  const eventExposureScore = computeEventExposureScore(macroEvidence)
  const score = clamp(
    (priceFlowScore * 0.35) + (regimeFitScore * 0.25) + (tickerSignalScore * 0.25) + (eventExposureScore * 0.15),
    -1,
    1,
  )

  return {
    sector,
    sectorLabel: getSectorLabel(sector),
    tickerCount: tickers.length,
    classification: 'neutral',
    fitLabel: getFitLabel(regimeFitScore, averageDailyChange),
    averageDailyChange,
    positiveTickerRatio,
    topGainer: getExtremeRef(refs, 'gain'),
    topLoser: getExtremeRef(refs, 'loss'),
    representativeTickers,
    priceFlowScore,
    regimeFitScore,
    tickerSignalScore,
    eventExposureScore,
    score,
    macroEvidence,
    rationale: buildRationale(regime, priceFlowScore, regimeFitScore, tickerSignalScore, eventExposureScore),
  }
}

function parseDailyChange(value: string | undefined): number | null {
  const trimmed = value?.trim()
  if (!trimmed || trimmed.toUpperCase() === 'N/A') return null

  const parsed = Number.parseFloat(trimmed.replace(/,/g, '').replace('%', ''))
  return Number.isFinite(parsed) ? parsed : null
}

function toTickerRef(ticker: TickerAnalysisData): SectorTickerRef {
  return {
    ticker: ticker.ticker,
    action: ticker.decision?.action,
    conviction: typeof ticker.decision?.conviction === 'number' ? ticker.decision.conviction : null,
    dailyChange: parseDailyChange(ticker.data_snapshot['Daily Change']),
  }
}

function compareTickerRefs(left: SectorTickerRef, right: SectorTickerRef): number {
  const actionDiff = actionRank(right.action) - actionRank(left.action)
  if (actionDiff !== 0) return actionDiff

  const convictionDiff = (right.conviction ?? -1) - (left.conviction ?? -1)
  if (convictionDiff !== 0) return convictionDiff

  return (right.dailyChange ?? -999) - (left.dailyChange ?? -999)
}

function actionRank(action: SectorTickerRef['action']): number {
  if (action === 'buy') return 3
  if (action === 'watch') return 2
  if (action === 'avoid') return 1
  return 0
}

function average(values: number[]): number | null {
  if (values.length === 0) return null
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function computePriceFlowScore(averageDailyChange: number | null, positiveTickerRatio: number | null): number {
  if (averageDailyChange === null && positiveTickerRatio === null) return 0

  const dailyScore = averageDailyChange === null ? 0 : clamp(averageDailyChange / 3, -1, 1)
  const breadthScore = positiveTickerRatio === null ? 0 : (positiveTickerRatio - 0.5) * 2
  return clamp((dailyScore * 0.45) + (breadthScore * 0.55), -1, 1)
}

function computeRegimeFitScore(tickers: TickerAnalysisData[]): number {
  const scores = tickers.flatMap((ticker) =>
    FACTOR_KEYS.flatMap((key) => {
      const value = ticker.decision?.factors?.[key]
      return typeof value === 'number' ? [normalizeFactorScore(key, value)] : []
    }),
  )

  return average(scores) ?? 0
}

function normalizeFactorScore(key: FactorScoreKey, value: number): number {
  const bounds = FACTOR_NORMALIZATION_BOUNDS[key]
  const bound = value < 0 ? bounds.negative : bounds.positive
  return clamp(value / bound, -1, 1)
}

function computeTickerSignalScore(refs: SectorTickerRef[]): number {
  const scores = refs.map((ref) => {
    const convictionWeight = ref.conviction === null ? 0.5 : clamp(ref.conviction / 100, 0, 1)
    if (ref.action === 'buy') return 0.4 + (convictionWeight * 0.6)
    if (ref.action === 'avoid') return -0.4 - (convictionWeight * 0.6)
    return 0
  })

  return average(scores) ?? 0
}

function findMacroEvidence(sector: string, macroContext: MacroContext | null | undefined): MacroEvent[] {
  const events = [
    ...(macroContext?.macro_events ?? []),
    ...(macroContext?.upcoming_macro_events ?? []),
  ]
  const needles = getSectorMatchKeys(sector)

  return events.filter((event) => {
    const fields = [
      ...(event.affected_sectors ?? []),
      ...(event.affected_industries ?? []),
      ...normalizeTags(event.sensitivity_tags),
    ]

    return fields.some((field) => hasSharedMatchKey(needles, getSectorMatchKeys(field)))
  })
}

function getSectorMatchKeys(value: string): Set<string> {
  const normalized = normalizeSectorText(value)
  const label = normalizeSectorText(getSectorLabel(value))
  const keys = new Set([normalized, label])
  const canonical = SECTOR_MATCH_ALIASES[normalized] ?? SECTOR_MATCH_ALIASES[label]
  if (canonical) keys.add(canonical)
  return keys
}

function normalizeSectorText(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, ' ')
}

function hasSharedMatchKey(left: Set<string>, right: Set<string>): boolean {
  for (const key of right) {
    if (left.has(key)) return true
  }
  return false
}

function normalizeTags(tags: string | string[] | undefined): string[] {
  if (!tags) return []
  if (Array.isArray(tags)) return tags
  return tags.split(',').map((tag) => tag.trim()).filter(Boolean)
}

function computeEventExposureScore(events: MacroEvent[]): number {
  if (events.length === 0) return 0

  const text = events
    .flatMap((event) => [
      event.label,
      event.summary_ko,
      event.market_bias,
      event.description,
      event.direction,
    ])
    .filter((value): value is string => Boolean(value))
    .join(' ')
    .toLowerCase()

  if (BEARISH_EVENT_PHRASES.some((phrase) => text.includes(phrase.toLowerCase()))) return -0.6
  if (POSITIVE_EVENT_PHRASES.some((phrase) => text.includes(phrase.toLowerCase()))) return 0.45
  if (NEGATIVE_EVENT_PHRASES.some((phrase) => text.includes(phrase.toLowerCase()))) return -0.6

  const hasHighImpact = events.some((event) => event.severity === 'high' || event.impact === 'high')
  return hasHighImpact ? -0.2 : 0.1
}

function getFitLabel(regimeFitScore: number, averageDailyChange: number | null): SectorFitLabel {
  if (averageDailyChange === null) return '확인 필요'
  if (regimeFitScore >= 0.25) return '정합 높음'
  if (regimeFitScore <= -0.25) return '정합 낮음'
  return '중립'
}

function getExtremeRef(refs: SectorTickerRef[], direction: 'gain' | 'loss'): SectorTickerRef | null {
  const withChange = refs.filter((ref) => ref.dailyChange !== null)
  if (withChange.length === 0) return null

  return withChange.reduce((selected, ref) => {
    if (selected.dailyChange === null || ref.dailyChange === null) return selected
    if (direction === 'gain') return ref.dailyChange > selected.dailyChange ? ref : selected
    return ref.dailyChange < selected.dailyChange ? ref : selected
  })
}

function isFocusCandidate(insight: SectorMoodInsight): boolean {
  return insight.score >= 0.12
    && insight.regimeFitScore > -0.2
    && insight.priceFlowScore > -0.35
}

function isWatchCandidate(insight: SectorMoodInsight): boolean {
  return insight.score <= -0.08
    || insight.regimeFitScore <= -0.3
    || insight.priceFlowScore <= -0.35
    || insight.eventExposureScore <= -0.35
}

function buildRationale(
  regime: MarketRegimeData | null | undefined,
  priceFlowScore: number,
  regimeFitScore: number,
  tickerSignalScore: number,
  eventExposureScore: number,
): string {
  const regimeText = regime?.regime ? `${regime.regime} 분위기` : '시장 분위기'

  if (eventExposureScore <= -0.35) {
    return '매크로 이벤트 노출이 있어 변동성과 상대강도를 확인할 섹터입니다.'
  }

  if (regimeFitScore <= -0.3) {
    return `${regimeText}와 정합도가 낮아 우선순위를 낮춰 확인합니다.`
  }

  if (priceFlowScore <= -0.35) {
    return '가격 흐름이 약해 반등 전까지 상대강도 점검이 필요합니다.'
  }

  if (priceFlowScore >= 0.2 && regimeFitScore >= 0) {
    return `${regimeText}와 가격 흐름이 같은 방향입니다.`
  }

  if (regimeFitScore >= 0.2 && tickerSignalScore >= 0.2) {
    return `${regimeText}와 종목 신호가 비교적 잘 맞습니다.`
  }

  if (priceFlowScore === 0) {
    return '일일 등락 데이터가 부족해 중립으로 표시합니다.'
  }

  return '흐름과 정합도 신호가 엇갈려 중립으로 확인합니다.'
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}
