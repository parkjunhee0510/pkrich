import type {
  NewsReference,
  SecFilingReference,
  SignalHistoryRow,
  SignalStats,
  TickerAnalysisData,
  UpcomingEvent,
} from '../types'
import { parsePrice } from './format'

export type SetupFocusLabel = '집중 모니터' | '관찰 우선' | '보류'
export type CatalystLevel = 'hard' | 'medium' | 'soft'

export interface TraderActionPlan {
  direction: string
  thesis: string
  entry: string
  invalidation: string
  nextCatalyst: string
}

export interface OptionsSignalTag {
  label: string
  tone?: 'bullish' | 'neutral' | 'bearish'
  emphasis?: 'normal' | 'alert'
}

export interface SetupScoreCard {
  ticker: string
  name: string
  score: number
  scoreSource: 'conviction' | 'setup'
  focusLabel: SetupFocusLabel
  actionPlan: TraderActionPlan
  earningsDday: string
  sectorRs: string
  forwardVsTtm: string
  latestBeatMiss: string
  beatStreak: number
  epsGrowth: string
  tags: string[]
  optionTags: OptionsSignalTag[]
  rawOptionsUnusualActivity: string
}

export interface EarningsBoardItem {
  ticker: string
  name: string
  dayLabel: string
  date: string
  timing: string
  beatMiss: string
  forwardVsTtm: string
  surprise: string
  signal: string
}

export interface EarningsBoardSection {
  key: string
  label: string
  items: EarningsBoardItem[]
}

export interface CatalystFeedItem {
  ticker: string
  name: string
  title: string
  link: string
  source: string
  publishedAt: string
  level: CatalystLevel
  tag: string
  note: string
  sortScore: number
}

export interface CatalystFeedSections {
  hard: CatalystFeedItem[]
  medium: CatalystFeedItem[]
  soft: CatalystFeedItem[]
}

export interface SignalPerformanceHighlight {
  label: string
  value: string
  note: string
}

export interface PositionSizingSummary {
  stopPrice: string
  positionShares: string
  riskReward: string
}

export interface PositioningGridItem {
  label: string
  value: string
  note: string
}

const THESIS_RECAP_PATTERN = /\b(why|how|what is|explained|recap|analysis of)\b/i
const OFFICIAL_SOURCE_PATTERN = /(newsroom|investor|ir|official|source)/i
const WIRES_SOURCE_PATTERN = /(reuters|associated press|ap news|ap\b|bloomberg)/i
const IMPORTANT_NEWS_PATTERN =
  /\b(earnings|guidance|outlook|forecast|results|upgrade|downgrade|buyback|dividend|contract|ceo|cfo|launch|approval)\b/i

export function buildSetupCards(tickers: TickerAnalysisData[], limit = 5): SetupScoreCard[] {
  return [...tickers]
    .map((ticker) => {
      const setup = computeSetupScore(ticker)
      const conviction = ticker.decision?.conviction
      const useConviction = typeof conviction === 'number'
      return {
        ticker: ticker.ticker,
        name: ticker.name,
        score: useConviction ? (conviction as number) : setup.score,
        scoreSource: (useConviction ? 'conviction' : 'setup') as 'conviction' | 'setup',
        focusLabel: setup.focusLabel,
        actionPlan: extractActionPlan(ticker),
        earningsDday: extractEarningsDdayLabel(ticker),
        sectorRs: ticker.price_action?.rs_vs_sector_etf ?? 'N/A',
        forwardVsTtm: ticker.earnings_setup?.forward_vs_ttm ?? 'N/A',
        latestBeatMiss: ticker.earnings_setup?.latest_beat_miss ?? 'N/A',
        beatStreak: ticker.earnings_pattern?.beat_streak ?? 0,
        epsGrowth: ticker.earnings_setup?.earnings_growth ?? 'N/A',
        tags: setup.tags.slice(0, 4),
        optionTags: buildOptionsSignalTags(ticker),
        rawOptionsUnusualActivity: ticker.options_summary?.unusual_activity ?? '',
      }
    })
    .sort((left, right) => right.score - left.score || left.ticker.localeCompare(right.ticker))
    .slice(0, limit)
}

export function computeSetupScore(ticker: TickerAnalysisData): { score: number; focusLabel: SetupFocusLabel; tags: string[] } {
  let score = 25
  const tags: string[] = []
  const earningsEvent = getNextEarningsEvent(ticker)
  const latestCatalyst = getLatestCatalystItem(ticker)
  const rvol = parseNumericValue(ticker.price_action?.relative_volume)
  const gap = parseNumericValue(ticker.price_action?.gap_percent)
  const rs = parseNumericValue(ticker.price_action?.rs_vs_spy)
  const forwardVsTtm = parseNumericValue(ticker.earnings_setup?.forward_vs_ttm)
  const beatMiss = ticker.earnings_setup?.latest_beat_miss ?? 'N/A'
  const shortFloat = parseNumericValue(ticker.fundamentals?.short_float_pct)
  const targetUpside = computeTargetUpsidePercent(ticker)
  const analystRecommendation = (ticker.fundamentals?.analyst_recommendation ?? '').toLowerCase()

  if (earningsEvent) {
    const daysUntil = parseInt(earningsEvent.days_until, 10)
    if (!Number.isNaN(daysUntil)) {
      if (daysUntil <= 3) score += 18
      else if (daysUntil <= 7) score += 14
      else if (daysUntil <= 21) score += 10
      else if (daysUntil <= 30) score += 6
      tags.push(`실적 D-${daysUntil}`)
    }
  }

  if (latestCatalyst) {
    if (latestCatalyst.level === 'hard') score += 20
    else if (latestCatalyst.level === 'medium') score += 10
    else score += 4
    tags.push(`${latestCatalyst.level} catalyst`)
  }

  if (rvol !== null) {
    if (rvol >= 1.5) score += 12
    else if (rvol >= 1.2) score += 8
    else if (rvol < 0.8) score -= 4
    if (rvol >= 1.2) tags.push(`RVOL ${rvol.toFixed(2)}x`)
  }

  if (gap !== null) {
    const absGap = Math.abs(gap)
    if (absGap >= 4) score += 10
    else if (absGap >= 2) score += 6
    if (absGap >= 2) tags.push(`Gap ${formatSignedPercent(gap)}`)
  }

  if (rs !== null) {
    if (rs >= 5) score += 12
    else if (rs >= 2) score += 8
    else if (rs <= -2) score -= 6
    if (rs >= 2) tags.push(`RS ${formatSignedPercent(rs)}`)
  }

  if (forwardVsTtm !== null) {
    if (forwardVsTtm >= 30) score += 10
    else if (forwardVsTtm >= 10) score += 6
    else if (forwardVsTtm <= -10) score -= 6
  }

  if (beatMiss === 'beat') score += 8
  if (beatMiss === 'miss') score -= 8
  if (beatMiss !== 'N/A') tags.push(`실적 ${beatMiss}`)

  if (shortFloat !== null && shortFloat >= 5) {
    score += 5
    tags.push(`공매도 ${shortFloat.toFixed(1)}%`)
  }

  if (analystRecommendation === 'strong buy' && targetUpside !== null && targetUpside >= 15) {
    score += 6
    tags.push(`목표가 +${targetUpside.toFixed(1)}%`)
  }

  score = Math.max(0, Math.min(100, Math.round(score)))
  const focusLabel: SetupFocusLabel = score >= 70 ? '집중 모니터' : score >= 50 ? '관찰 우선' : '보류'
  return { score, focusLabel, tags }
}

export function extractActionPlan(ticker: TickerAnalysisData): TraderActionPlan {
  const signalText = (ticker.signal_or_takeaway ?? '').trim()
  const [headPart, ...detailParts] = signalText.split('|').map((part) => part.trim())
  const detailPart = detailParts.join(' | ')
  const dashMatch = headPart.match(/^(.*?)\s*[—-]\s*(.+)$/)
  const direction = dashMatch?.[1]?.trim() || '중립 관찰'
  const thesis = dashMatch?.[2]?.trim() || headPart || '핵심 촉매 확인'
  const entry = extractMatchedValue(detailPart, /진입존\s*([^/|]+)/i) || inferEntryZone(ticker)
  const invalidation =
    extractMatchedValue(detailPart, /무효화\s*(.+)$/i) ||
    ticker.trade_frame?.invalidation_price ||
    '핵심 지지선 확인 필요'
  const nextCatalyst = formatNextCatalyst(ticker)

  return { direction, thesis, entry, invalidation, nextCatalyst }
}


type ParsedUnusualContract = {
  side: 'PUT' | 'CALL'
  strike: string
  volume: number
  ratio: number | null
}

export type UnusualActivityPostureTone = 'defensive' | 'bullish' | 'mixed'
export type UnusualActivityStrengthTone = 'normal' | 'strong' | 'very-strong'

export interface UnusualActivityMeta {
  postureLabel: string
  postureTone: UnusualActivityPostureTone
  strengthLabel: string | null
  strengthTone: UnusualActivityStrengthTone
}

export function summarizeUnusualActivity(value?: string): string {
  const parsed = parseUnusualContracts(value)
  if (parsed.length === 0) {
    return '이상 거래 해석에 필요한 옵션 흐름이 아직 충분하지 않습니다.'
  }

  const putCount = parsed.filter((item) => item.side === 'PUT').length
  const callCount = parsed.filter((item) => item.side === 'CALL').length
  const dominantSide = putCount > callCount ? 'put' : callCount > putCount ? 'call' : 'mixed'
  const strongest = [...parsed].sort((left, right) => (right.ratio ?? 0) - (left.ratio ?? 0))[0]
  const dominantStrike = mostCommonStrike(parsed, dominantSide === 'mixed' ? undefined : dominantSide.toUpperCase() as 'PUT' | 'CALL')
  const postureTag = getUnusualPostureTag(dominantSide)

  const lead = dominantSide === 'put'
    ? `${postureTag} 풋 수요가 우세합니다.`
    : dominantSide === 'call'
      ? `${postureTag} 콜 수요가 우세합니다.`
      : `${postureTag} 콜/풋 양방향 포지셔닝이 함께 붙었습니다.`

  const strikeNote = dominantStrike
    ? `${dominantStrike} 행사가 중심으로 거래가 몰렸습니다.`
    : '행사가가 한쪽으로 크게 쏠리지는 않았습니다.'
  const strengthNote = strongest?.ratio !== null && strongest?.ratio !== undefined
    ? `가장 강한 계약은 OI 대비 ${Math.round(strongest.ratio)}%로 ${describeUnusualStrength(strongest.ratio)}.`
    : '강도 판단에 필요한 OI 비율 정보는 제한적입니다.'

  return `${lead} ${strikeNote} ${strengthNote}`
}

export function summarizeUnusualActivityShort(value?: string): string {
  const parsed = parseUnusualContracts(value)
  if (parsed.length === 0) {
    return ''
  }
  const putCount = parsed.filter((item) => item.side === 'PUT').length
  const callCount = parsed.filter((item) => item.side === 'CALL').length
  const dominantSide = putCount > callCount ? 'put' : callCount > putCount ? 'call' : 'mixed'
  const strongest = [...parsed].sort((left, right) => (right.ratio ?? 0) - (left.ratio ?? 0))[0]
  const dominantStrike = mostCommonStrike(parsed, dominantSide === 'mixed' ? undefined : dominantSide.toUpperCase() as 'PUT' | 'CALL')

  const lead = getUnusualPostureShortLabel(dominantSide)
  const strikeNote = dominantStrike ? `${dominantStrike} 가격대 집중` : '가격대 분산'
  const strengthNote = strongest?.ratio !== null && strongest?.ratio !== undefined
    ? `보유량 대비 ${Math.round(strongest.ratio)}%`
    : ''

  return [lead, strikeNote, strengthNote].filter(Boolean).join(' · ')
}

export function getUnusualActivityMeta(value?: string): UnusualActivityMeta | null {
  const parsed = parseUnusualContracts(value)
  if (parsed.length === 0) {
    return null
  }

  const putCount = parsed.filter((item) => item.side === 'PUT').length
  const callCount = parsed.filter((item) => item.side === 'CALL').length
  const dominantSide = putCount > callCount ? 'put' : callCount > putCount ? 'call' : 'mixed'
  const strongest = [...parsed].sort((left, right) => (right.ratio ?? 0) - (left.ratio ?? 0))[0]

  return {
    postureLabel: getUnusualPostureTag(dominantSide),
    postureTone: getUnusualPostureTone(dominantSide),
    strengthLabel: getUnusualStrengthLabel(strongest?.ratio ?? null),
    strengthTone: getUnusualStrengthTone(strongest?.ratio ?? null),
  }
}

function getUnusualPostureTag(side: 'put' | 'call' | 'mixed'): string {
  if (side === 'put') return '단기 하방 방어'
  if (side === 'call') return '상승 베팅'
  return '변동성 대응'
}

function getUnusualPostureShortLabel(side: 'put' | 'call' | 'mixed'): string {
  if (side === 'put') return '하락 대비'
  if (side === 'call') return '상승 기대'
  return '방향성 혼재'
}

function getUnusualPostureTone(side: 'put' | 'call' | 'mixed'): UnusualActivityPostureTone {
  if (side === 'put') return 'defensive'
  if (side === 'call') return 'bullish'
  return 'mixed'
}

function getUnusualStrengthLabel(ratio: number | null): string | null {
  if (ratio === null) return null
  if (ratio >= 80) return '매우 강함'
  if (ratio >= 50) return '강함'
  return null
}

function getUnusualStrengthTone(ratio: number | null): UnusualActivityStrengthTone {
  if (ratio === null) return 'normal'
  if (ratio >= 80) return 'very-strong'
  if (ratio >= 50) return 'strong'
  return 'normal'
}

function parseUnusualContracts(value?: string): ParsedUnusualContract[] {
  if (!value) return []
  return value
    .split(';')
    .map((segment) => segment.trim())
    .filter(Boolean)
    .map((segment) => {
      const sideMatch = segment.match(/\b(PUT|CALL)\b/i)
      const strikeMatch = segment.match(/\$\s*([0-9]+(?:\.[0-9]+)?)/)
      const volumeMatch = segment.match(/vol\s*([0-9,]+)/i)
      const ratioMatch = segment.match(/([0-9]+(?:\.[0-9]+)?)%/)
      if (!sideMatch || !strikeMatch) {
        return null
      }
      return {
        side: sideMatch[1].toUpperCase() as 'PUT' | 'CALL',
        strike: `$${strikeMatch[1]}`,
        volume: volumeMatch ? Number.parseInt(volumeMatch[1].replace(/,/g, ''), 10) : 0,
        ratio: ratioMatch ? Number.parseFloat(ratioMatch[1]) : null,
      }
    })
    .filter((item): item is ParsedUnusualContract => item !== null)
}

function mostCommonStrike(items: ParsedUnusualContract[], side?: 'PUT' | 'CALL'): string | null {
  const counts = new Map<string, number>()
  for (const item of items) {
    if (side && item.side !== side) continue
    counts.set(item.strike, (counts.get(item.strike) ?? 0) + 1)
  }
  let best: string | null = null
  let bestCount = 0
  for (const [strike, count] of counts.entries()) {
    if (count > bestCount) {
      best = strike
      bestCount = count
    }
  }
  return best
}

function describeUnusualStrength(ratio: number): string {
  if (ratio >= 80) return '매우 공격적인 수준입니다'
  if (ratio >= 50) return '상당히 강한 편입니다'
  if (ratio >= 30) return '눈에 띄는 수준입니다'
  return '경계해 볼 정도입니다'
}

export function formatOptionsToneLabel(value?: string): string {
  if (value === 'bullish') return '옵션 강세'
  if (value === 'bearish') return '옵션 약세'
  return '옵션 중립'
}

export function buildOptionsSignalTags(ticker: TickerAnalysisData): OptionsSignalTag[] {
  const summary = ticker.options_summary
  if (!summary) {
    return []
  }

  const tags: OptionsSignalTag[] = []
  const tone = (summary.tone ?? '').trim()
  if (tone && tone !== 'N/A') {
    const normalizedTone = tone === 'bullish' || tone === 'bearish' ? tone : 'neutral'
    tags.push({
      label: formatOptionsToneLabel(normalizedTone),
      tone: normalizedTone,
      emphasis: 'normal',
    })
  }

  if (summary.unusual_activity && summary.unusual_activity !== 'N/A') {
    tags.push({ label: '이상 거래', emphasis: 'alert' })
  }

  return tags
}

export function buildPriceActionTags(ticker: TickerAnalysisData): string[] {
  const tags: string[] = []
  const vsSma50 = parseNumericValue(ticker.price_action?.price_vs_sma50)
  const vsSma200 = parseNumericValue(ticker.price_action?.price_vs_sma200)
  const week52 = parseNumericValue(ticker.price_action?.week52_position)
  const rvol = parseNumericValue(ticker.price_action?.relative_volume)
  const gap = parseNumericValue(ticker.price_action?.gap_percent)
  const rs = parseNumericValue(ticker.price_action?.rs_vs_spy)
  const sectorRs = parseNumericValue(ticker.price_action?.rs_vs_sector_etf)

  if (vsSma50 !== null && vsSma200 !== null) {
    if (vsSma50 > 2 && vsSma200 > 0) tags.push('추세 우위')
    else if (vsSma50 < -2 && vsSma200 < 0) tags.push('추세 약세')
  }

  if (week52 !== null) {
    if (week52 >= 85) tags.push('상단 돌파권')
    else if (week52 <= 20) tags.push('저점 반등권')
  }

  if (rvol !== null) {
    if (rvol >= 1.2) tags.push('거래량 유입')
    else if (rvol < 0.8) tags.push('거래량 부진')
  }

  if (gap !== null) {
    if (gap >= 3) tags.push('갭 업')
    else if (gap <= -3) tags.push('갭 다운')
  }

  if (rs !== null) {
    if (rs >= 2) tags.push('상대강도 우위')
    else if (rs <= -2) tags.push('상대약세')
  }

  if (sectorRs !== null) {
    if (sectorRs >= 2) tags.push('섹터 우위')
    else if (sectorRs <= -2) tags.push('섹터 약세')
  }

  return tags.slice(0, 4)
}

export function buildEarningsBoardSections(tickers: TickerAnalysisData[]): EarningsBoardSection[] {
  const sections: EarningsBoardSection[] = [
    { key: 'today', label: '오늘', items: [] },
    { key: 'd3', label: 'D-3', items: [] },
    { key: 'd7', label: 'D-7', items: [] },
    { key: 'd21', label: 'D-21', items: [] },
  ]

  for (const ticker of tickers) {
    const earningsEvent = getNextEarningsEvent(ticker)
    if (!earningsEvent) {
      continue
    }

    const days = parseInt(earningsEvent.days_until, 10)
    if (Number.isNaN(days) || days < 0 || days > 21) {
      continue
    }

    const item: EarningsBoardItem = {
      ticker: ticker.ticker,
      name: ticker.name,
      dayLabel: days === 0 ? '오늘' : `D-${days}`,
      date: earningsEvent.date,
      timing: earningsEvent.timing ?? '',
      beatMiss: ticker.earnings_setup?.latest_beat_miss ?? 'N/A',
      forwardVsTtm: ticker.earnings_setup?.forward_vs_ttm ?? 'N/A',
      surprise: ticker.earnings_setup?.latest_surprise_pct ?? 'N/A',
      signal: extractActionPlan(ticker).direction,
    }

    if (days === 0) sections[0].items.push(item)
    else if (days <= 3) sections[1].items.push(item)
    else if (days <= 7) sections[2].items.push(item)
    else sections[3].items.push(item)
  }

  return sections.map((section) => ({
    ...section,
    items: section.items.sort((left, right) => left.date.localeCompare(right.date) || left.ticker.localeCompare(right.ticker)),
  }))
}

export function buildCatalystFeedSections(tickers: TickerAnalysisData[], limitPerLevel = 6): CatalystFeedSections {
  const items = tickers.flatMap((ticker) => buildCatalystFeedItemsForTicker(ticker))
  const deduped = dedupeCatalystFeedItems(items)
  const sortDesc = (left: CatalystFeedItem, right: CatalystFeedItem) =>
    right.sortScore - left.sortScore || parsePublishedAt(right.publishedAt) - parsePublishedAt(left.publishedAt)

  return {
    hard: deduped.filter((item) => item.level === 'hard').sort(sortDesc).slice(0, limitPerLevel),
    medium: deduped.filter((item) => item.level === 'medium').sort(sortDesc).slice(0, limitPerLevel),
    soft: deduped.filter((item) => item.level === 'soft').sort(sortDesc).slice(0, limitPerLevel),
  }
}

export function buildSignalPerformanceHighlights(signalStats?: SignalStats): SignalPerformanceHighlight[] {
  if (!signalStats) {
    return []
  }

  const bullSummary = signalStats.summary_by_direction?.bull
  const bearSummary = signalStats.summary_by_direction?.bear
  const highlights: SignalPerformanceHighlight[] = []

  if (bullSummary) {
    highlights.push({
      label: '강세 5D 승률',
      value: bullSummary.win_rate_5d || 'N/A',
      note: `${bullSummary.evaluated_5d}건 평가 / 평균 ${bullSummary.avg_return_5d || 'N/A'}`,
    })
  }

  if (bearSummary) {
    highlights.push({
      label: '약세 5D 승률',
      value: bearSummary.win_rate_5d || 'N/A',
      note: `${bearSummary.evaluated_5d}건 평가 / 평균 ${bearSummary.avg_return_5d || 'N/A'}`,
    })
  }

  const hardSignals = signalStats.recent_signals.filter((signal) => isHardSignal(signal) && signal.evaluated_1d === 'True')
  const beatSignals = signalStats.recent_signals.filter((signal) => /beat/i.test(signal.catalyst_tag) && signal.evaluated_5d === 'True')

  if (hardSignals.length > 0) {
    highlights.push({
      label: 'Hard Catalyst 1D 평균',
      value: formatAverageReturn(hardSignals, 'return_1d'),
      note: `${hardSignals.length}건 기준`,
    })
  }

  if (beatSignals.length > 0) {
    highlights.push({
      label: 'Beat Setup 5D 평균',
      value: formatAverageReturn(beatSignals, 'return_5d'),
      note: `${beatSignals.length}건 기준`,
    })
  }

  return highlights
}

export function buildDashboardPositioningSummary(ticker: TickerAnalysisData): string {
  const fundamentals = ticker.fundamentals ?? {}
  const shortFloat = fundamentals.short_float_pct ?? 'N/A'
  const analyst = fundamentals.analyst_recommendation ?? 'N/A'
  const target = fundamentals.analyst_target_price ?? 'N/A'
  return `${shortFloat} | ${analyst} | 목표 ${target}`
}

export function buildPositioningGrid(ticker: TickerAnalysisData): PositioningGridItem[] {
  const fundamentals = ticker.fundamentals ?? {}
  const shortFloat = fundamentals.short_float_pct ?? 'N/A'
  const shortRatio = fundamentals.short_ratio ?? 'N/A'
  const analyst = fundamentals.analyst_recommendation ?? 'N/A'
  const analystCount = fundamentals.analyst_count ?? 'N/A'
  const target = fundamentals.analyst_target_price ?? 'N/A'
  const institutions = fundamentals.held_by_institutions ?? 'N/A'
  const impliedVolatility = fundamentals.implied_volatility ?? 'N/A'

  return [
    {
      label: '공매도',
      value: shortFloat,
      note: shortRatio !== 'N/A' ? `커버 ${shortRatio}` : '커버링 일수 미확인',
    },
    {
      label: '애널리스트',
      value: analyst,
      note: `${analystCount}, 목표 ${target}`,
    },
    {
      label: '기관 보유',
      value: institutions,
      note: '스마트머니 포지션',
    },
    {
      label: '옵션 IV',
      value: impliedVolatility,
      note: '연환산 내재변동성',
    },
  ]
}

export function buildPositionSizingSummary(ticker: TickerAnalysisData, accountSize = 10000): PositionSizingSummary {
  const price = parsePrice(ticker.data_snapshot['Price'] ?? 'N/A')
  const atr = parseNumericValue(ticker.price_action?.atr_14d)
  const currency = extractCurrency(ticker.data_snapshot['Price'] ?? 'USD')
  if (!price || !atr || atr <= 0) {
    return { stopPrice: 'N/A', positionShares: 'N/A', riskReward: 'N/A' }
  }

  const riskBudget = accountSize * 0.01
  const shares = Math.max(0, Math.floor(riskBudget / atr))
  const stopPrice = price - (2 * atr)
  const targetPrice = parsePrice(ticker.fundamentals?.analyst_target_price ?? 'N/A')
  let riskReward: string
  if (targetPrice > 0 && targetPrice <= price) {
    riskReward = `목표 ${targetPrice.toFixed(2)} / 현재 ${price.toFixed(2)}`
  } else if (targetPrice > price) {
    const reward = targetPrice - price
    const risk = atr * 2
    riskReward = risk > 0 ? `${(reward / risk).toFixed(2)}R` : 'N/A'
  } else {
    riskReward = 'N/A'
  }

  return {
    stopPrice: `${stopPrice.toFixed(2)} ${currency}`,
    positionShares: `${shares}주`,
    riskReward,
  }
}

export function computeTargetUpsidePercent(ticker: TickerAnalysisData): number | null {
  const price = parsePrice(ticker.data_snapshot['Price'] ?? 'N/A')
  const targetPrice = parsePrice(ticker.fundamentals?.analyst_target_price ?? 'N/A')
  if (!price || !targetPrice || targetPrice <= 0) {
    return null
  }
  return ((targetPrice - price) / price) * 100
}

export function extractEarningsDdayLabel(ticker: TickerAnalysisData): string {
  const event = getNextEarningsEvent(ticker)
  if (!event) {
    return 'N/A'
  }
  const dayPart = `D-${event.days_until}`
  return event.timing ? `${dayPart} · ${event.timing}` : dayPart
}

export function getNextEarningsEvent(ticker: TickerAnalysisData): UpcomingEvent | undefined {
  return [...(ticker.upcoming_events ?? [])]
    .filter((event) => event.type === 'earnings')
    .sort((left, right) => parseInt(left.days_until, 10) - parseInt(right.days_until, 10))[0]
}

export function getLatestCatalystItem(ticker: TickerAnalysisData): CatalystFeedItem | null {
  return buildCatalystFeedItemsForTicker(ticker).sort((left, right) =>
    right.sortScore - left.sortScore || parsePublishedAt(right.publishedAt) - parsePublishedAt(left.publishedAt),
  )[0] ?? null
}

function buildCatalystFeedItemsForTicker(ticker: TickerAnalysisData): CatalystFeedItem[] {
  const filingItems = (ticker.sec_filings ?? []).map((filing) => secFilingToFeedItem(ticker, filing))
  const newsItems = (ticker.news_references ?? []).map((reference) => newsReferenceToFeedItem(ticker, reference))
  return [...filingItems, ...newsItems]
}

function secFilingToFeedItem(ticker: TickerAnalysisData, filing: SecFilingReference): CatalystFeedItem {
  const level = (filing.catalyst_type as CatalystLevel) || 'medium'
  const recency = recencyScore(filing.published_at, level)
  return {
    ticker: ticker.ticker,
    name: ticker.name,
    title: filing.title,
    link: filing.link,
    source: filing.source,
    publishedAt: filing.published_at,
    level,
    tag: filing.tag || filing.form_type || 'SEC 공시',
    note: `${filing.form_type}${filing.item_number ? ` Item ${filing.item_number}` : ''}`.trim(),
    sortScore: (filing.importance_score ?? 100) + recency,
  }
}

function newsReferenceToFeedItem(ticker: TickerAnalysisData, reference: NewsReference): CatalystFeedItem {
  const normalizedSource = reference.source.toLowerCase()
  const normalizedTitle = reference.title.toLowerCase()
  let level: CatalystLevel = 'soft'
  let baseScore = 45
  let note = '일반 뉴스'

  if (OFFICIAL_SOURCE_PATTERN.test(reference.source)) {
    level = 'hard'
    baseScore = 150
    note = '공식 발표'
  } else if (WIRES_SOURCE_PATTERN.test(normalizedSource) || IMPORTANT_NEWS_PATTERN.test(normalizedTitle)) {
    level = 'medium'
    baseScore = 95
    note = '속보 / 핵심 헤드라인'
  }

  if (THESIS_RECAP_PATTERN.test(normalizedTitle)) {
    baseScore -= 30
    note = '해설성 기사'
  }

  return {
    ticker: ticker.ticker,
    name: ticker.name,
    title: reference.title,
    link: reference.link,
    source: reference.source,
    publishedAt: reference.published_at,
    level,
    tag: level === 'hard' ? '공식/공시' : level === 'medium' ? '속보' : '소프트',
    note,
    sortScore: baseScore + recencyScore(reference.published_at, level),
  }
}

function dedupeCatalystFeedItems(items: CatalystFeedItem[]): CatalystFeedItem[] {
  const seen = new Set<string>()
  const deduped: CatalystFeedItem[] = []
  for (const item of items) {
    const key = `${item.ticker}::${item.title.trim().toLowerCase()}`
    if (seen.has(key)) {
      continue
    }
    seen.add(key)
    deduped.push(item)
  }
  return deduped
}

function recencyScore(publishedAt: string, level: CatalystLevel): number {
  const now = Date.now()
  const publishedMs = parsePublishedAt(publishedAt)
  if (publishedMs === 0) {
    return 0
  }
  const daysOld = Math.max(0, Math.floor((now - publishedMs) / 86_400_000))
  if (level === 'hard') return Math.max(0, 30 - daysOld)
  if (level === 'medium') return Math.max(0, 14 - daysOld)
  return Math.max(0, 7 - daysOld)
}

function parsePublishedAt(value: string): number {
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? 0 : parsed
}

function formatNextCatalyst(ticker: TickerAnalysisData): string {
  const earningsEvent = getNextEarningsEvent(ticker)
  if (earningsEvent) {
    const suffix = earningsEvent.timing ? ` · ${earningsEvent.timing}` : ''
    return `${earningsEvent.label} D-${earningsEvent.days_until}${suffix}`
  }
  const latestCatalyst = getLatestCatalystItem(ticker)
  if (latestCatalyst) {
    return `${latestCatalyst.tag} / ${latestCatalyst.source}`
  }
  return '다음 촉매 대기'
}

function inferEntryZone(ticker: TickerAnalysisData): string {
  const price = parsePrice(ticker.data_snapshot['Price'] ?? 'N/A')
  const atr = parseNumericValue(ticker.price_action?.atr_14d)
  if (!price || !atr) {
    return '가격대 확인 필요'
  }
  return `${(price - atr).toFixed(2)}-${(price + atr).toFixed(2)}`
}

function extractMatchedValue(source: string, pattern: RegExp): string {
  const match = source.match(pattern)
  return match?.[1]?.trim() ?? ''
}

function parseNumericValue(value?: string): number | null {
  if (!value) return null
  const numeric = value.replace(/,/g, '').match(/[-+]?\d*\.?\d+/)
  if (!numeric) return null
  const parsed = Number.parseFloat(numeric[0])
  return Number.isNaN(parsed) ? null : parsed
}

function formatSignedPercent(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

function isHardSignal(signal: SignalHistoryRow): boolean {
  return /(실적|8-k|10-q|10-k|20-f|ceo|cfo|guidance|item 2\.02|item 5\.02)/i.test(signal.catalyst_tag)
}

function formatAverageReturn(rows: SignalHistoryRow[], field: 'return_1d' | 'return_5d' | 'return_20d'): string {
  const values = rows
    .map((row) => Number.parseFloat(row[field]))
    .filter((value) => !Number.isNaN(value))
  if (values.length === 0) {
    return 'N/A'
  }
  const avg = values.reduce((sum, value) => sum + value, 0) / values.length
  return `${avg >= 0 ? '+' : ''}${avg.toFixed(2)}%`
}

function extractCurrency(value: string): string {
  const tokens = value.trim().split(/\s+/)
  const tail = tokens[tokens.length - 1]
  return /^[A-Z]{3,5}$/.test(tail) ? tail : 'USD'
}
