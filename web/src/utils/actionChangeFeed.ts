import type { DailyEntry, TickerAnalysisData, TickerDecisionData } from '../types'
import { classifyDecisionQuality } from './decisionQuality'
import { buildSearchEvidenceBadge, type SearchEvidenceBadgeData } from './searchEvidenceBadge'

export type ActionChangeType = 'action_change' | 'conviction_change' | 'new_ticker' | 'risk_added'
export type ActionChangeTone = 'positive' | 'negative' | 'caution' | 'neutral' | 'info'
export type DecisionAction = TickerDecisionData['action']

export interface ActionChangeFeedEntry {
  id: string
  type: ActionChangeType
  tone: ActionChangeTone
  ticker: string
  name: string
  sector: string
  previousAction?: DecisionAction
  currentAction?: DecisionAction
  previousConviction: number | null
  currentConviction: number | null
  convictionDelta: number | null
  addedRisks: string[]
  primaryLabel: string
  secondaryLabel: string
  qualityDetail?: string
  qualityClassName?: string
  metricLabel?: string | null
  summary: string
  evidenceBadge?: SearchEvidenceBadgeData
}

export interface ActionChangeFeedResult {
  currentDate: string
  previousDate: string | null
  hasPreviousDay: boolean
  entries: ActionChangeFeedEntry[]
}

export interface BuildActionChangeFeedOptions {
  convictionDeltaThreshold?: number
}

const DEFAULT_CONVICTION_DELTA_THRESHOLD = 10

const ACTION_LABELS: Record<DecisionAction, string> = {
  buy: 'BUY',
  watch: 'WATCH',
  avoid: 'AVOID',
}

const ACTION_RANK: Record<DecisionAction, number> = {
  avoid: 0,
  watch: 1,
  buy: 2,
}

const TYPE_RANK: Record<ActionChangeType, number> = {
  action_change: 0,
  conviction_change: 1,
  new_ticker: 2,
  risk_added: 3,
}

export function findPreviousValidDay(days: DailyEntry[], selectedIndex: number): DailyEntry | null {
  const startIndex = Math.min(selectedIndex - 1, days.length - 1)

  for (let index = startIndex; index >= 0; index -= 1) {
    const day = days[index]
    if (Array.isArray(day?.tickers) && day.tickers.length > 0) {
      return day
    }
  }

  return null
}

export function buildActionChangeFeed(
  currentDay: DailyEntry,
  previousDay: DailyEntry | null | undefined,
  options: BuildActionChangeFeedOptions = {},
): ActionChangeFeedResult {
  if (!previousDay) {
    return {
      currentDate: currentDay.date,
      previousDate: null,
      hasPreviousDay: false,
      entries: [],
    }
  }

  const convictionDeltaThreshold = resolveConvictionDeltaThreshold(
    options.convictionDeltaThreshold,
  )
  const previousByTicker = new Map(
    previousDay.tickers.map((ticker) => [normalizeTicker(ticker.ticker), ticker]),
  )

  const entries = currentDay.tickers
    .map((currentTicker) =>
      buildEntry(
        currentTicker,
        previousByTicker.get(normalizeTicker(currentTicker.ticker)),
        convictionDeltaThreshold,
      ),
    )
    .filter((entry): entry is ActionChangeFeedEntry => entry !== null)
    .sort(compareEntries)

  return {
    currentDate: currentDay.date,
    previousDate: previousDay.date,
    hasPreviousDay: true,
    entries,
  }
}

function buildEntry(
  currentTicker: TickerAnalysisData,
  previousTicker: TickerAnalysisData | undefined,
  convictionDeltaThreshold: number,
): ActionChangeFeedEntry | null {
  const currentDecision = currentTicker.decision
  const previousDecision = previousTicker?.decision
  const currentAction = currentDecision?.action
  const previousAction = previousDecision?.action
  const currentConviction = numericConviction(currentTicker)
  const previousConviction = previousTicker ? numericConviction(previousTicker) : null
  const convictionDelta =
    currentConviction !== null && previousConviction !== null
      ? currentConviction - previousConviction
      : null
  const addedRisks = findAddedRisks(
    currentTicker.risks_or_watchpoints,
    previousTicker?.risks_or_watchpoints ?? [],
  )

  if (!previousTicker) {
    return createEntry('new_ticker', currentTicker, previousTicker, addedRisks, convictionDelta)
  }

  if (currentAction && previousAction && currentAction !== previousAction) {
    return createEntry('action_change', currentTicker, previousTicker, addedRisks, convictionDelta)
  }

  if (
    currentDecision &&
    previousDecision &&
    currentAction === previousAction &&
    convictionDelta !== null &&
    Math.abs(convictionDelta) >= convictionDeltaThreshold
  ) {
    return createEntry('conviction_change', currentTicker, previousTicker, addedRisks, convictionDelta)
  }

  if (addedRisks.length > 0) {
    return createEntry('risk_added', currentTicker, previousTicker, addedRisks, convictionDelta)
  }

  return null
}

function createEntry(
  type: ActionChangeType,
  currentTicker: TickerAnalysisData,
  previousTicker: TickerAnalysisData | undefined,
  addedRisks: string[],
  convictionDelta: number | null,
): ActionChangeFeedEntry {
  const previousAction = previousTicker?.decision?.action
  const currentAction = currentTicker.decision?.action
  const previousConviction = previousTicker ? numericConviction(previousTicker) : null
  const currentConviction = numericConviction(currentTicker)
  const ticker = normalizeTicker(currentTicker.ticker)
  const quality = classifyDecisionQuality(currentTicker)

  return {
    id: `${type}-${ticker}`,
    type,
    tone: toneForEntry(type, previousAction, currentAction, convictionDelta),
    ticker,
    name: currentTicker.name,
    sector: currentTicker.data_snapshot?.Sector ?? 'Unknown',
    previousAction,
    currentAction,
    previousConviction,
    currentConviction,
    convictionDelta,
    addedRisks,
    primaryLabel: primaryLabelFor(type, previousAction, currentAction, convictionDelta, addedRisks),
    secondaryLabel: secondaryLabelFor(previousConviction, currentConviction, convictionDelta),
    qualityDetail: quality.score === null ? undefined : quality.detail,
    qualityClassName: quality.className,
    metricLabel: metricLabelFor(convictionDelta, addedRisks),
    summary: summaryFor(currentTicker, addedRisks),
    evidenceBadge: buildSearchEvidenceBadge(currentTicker),
  }
}

function compareEntries(left: ActionChangeFeedEntry, right: ActionChangeFeedEntry): number {
  const typeDiff = TYPE_RANK[left.type] - TYPE_RANK[right.type]
  if (typeDiff !== 0) return typeDiff

  const leftDelta = Math.abs(left.convictionDelta ?? 0)
  const rightDelta = Math.abs(right.convictionDelta ?? 0)
  if (leftDelta !== rightDelta) return rightDelta - leftDelta

  const leftConviction = left.currentConviction ?? -1
  const rightConviction = right.currentConviction ?? -1
  if (leftConviction !== rightConviction) return rightConviction - leftConviction

  return left.ticker.localeCompare(right.ticker)
}

function resolveConvictionDeltaThreshold(threshold: number | undefined): number {
  if (threshold === undefined) {
    return DEFAULT_CONVICTION_DELTA_THRESHOLD
  }

  return Number.isFinite(threshold) && threshold >= 0
    ? threshold
    : DEFAULT_CONVICTION_DELTA_THRESHOLD
}

function primaryLabelFor(
  type: ActionChangeType,
  previousAction: DecisionAction | undefined,
  currentAction: DecisionAction | undefined,
  convictionDelta: number | null,
  addedRisks: string[],
): string {
  if (type === 'action_change' && previousAction && currentAction) {
    return `${ACTION_LABELS[previousAction]} -> ${ACTION_LABELS[currentAction]}`
  }

  if (type === 'conviction_change' && convictionDelta !== null) {
    return formatDelta(convictionDelta)
  }

  if (type === 'new_ticker') {
    return currentAction ? `NEW ${ACTION_LABELS[currentAction]}` : 'NEW'
  }

  return `NEW RISK x${addedRisks.length}`
}

function secondaryLabelFor(
  previousConviction: number | null,
  currentConviction: number | null,
  convictionDelta: number | null,
): string {
  if (previousConviction !== null && currentConviction !== null && convictionDelta !== null) {
    return `Conviction ${previousConviction} -> ${currentConviction} (${formatDelta(convictionDelta)})`
  }

  if (currentConviction !== null) {
    return `Conviction ${currentConviction}`
  }

  return 'Conviction N/A'
}

function metricLabelFor(convictionDelta: number | null, addedRisks: string[]): string | null {
  if (convictionDelta !== null) {
    return formatDelta(convictionDelta)
  }

  if (addedRisks.length > 0) {
    return `risk x${addedRisks.length}`
  }

  return null
}

function toneForEntry(
  type: ActionChangeType,
  previousAction: DecisionAction | undefined,
  currentAction: DecisionAction | undefined,
  convictionDelta: number | null,
): ActionChangeTone {
  if (type === 'action_change' && previousAction && currentAction) {
    if (ACTION_RANK[currentAction] > ACTION_RANK[previousAction]) return 'positive'
    if (ACTION_RANK[currentAction] < ACTION_RANK[previousAction]) return 'negative'
    return 'neutral'
  }

  if (type === 'conviction_change') {
    if ((convictionDelta ?? 0) > 0) return 'positive'
    if ((convictionDelta ?? 0) < 0) return 'caution'
    return 'neutral'
  }

  if (type === 'new_ticker') {
    if (currentAction === 'buy') return 'positive'
    if (currentAction === 'avoid') return 'negative'
    return 'info'
  }

  return 'caution'
}

function summaryFor(currentTicker: TickerAnalysisData, addedRisks: string[]): string {
  return firstNonEmpty([
    currentTicker.decision?.reason,
    addedRisks[0],
    currentTicker.signal_or_takeaway,
    currentTicker.summary,
    'No change explanation available.',
  ])
}

function findAddedRisks(currentRisks: string[] = [], previousRisks: string[] = []): string[] {
  const previousRiskKeys = new Set(previousRisks.map(normalizeRisk).filter(Boolean))
  const seenCurrentRiskKeys = new Set<string>()
  const addedRisks: string[] = []

  for (const risk of currentRisks) {
    const riskKey = normalizeRisk(risk)
    if (!riskKey || previousRiskKeys.has(riskKey) || seenCurrentRiskKeys.has(riskKey)) {
      continue
    }

    seenCurrentRiskKeys.add(riskKey)
    addedRisks.push(formatRiskForDisplay(risk))
  }

  return addedRisks
}

function numericConviction(ticker: TickerAnalysisData): number | null {
  const conviction = ticker.decision?.conviction
  return typeof conviction === 'number' && Number.isFinite(conviction) ? conviction : null
}

function normalizeTicker(ticker: string): string {
  return ticker.trim().toUpperCase()
}

function normalizeRisk(risk: string): string {
  return risk.trim().replace(/\s+/g, ' ').toLowerCase()
}

function formatRiskForDisplay(risk: string): string {
  return risk.trim().replace(/\s+/g, ' ')
}

function formatDelta(delta: number): string {
  return `${delta >= 0 ? '+' : ''}${delta}p`
}

function firstNonEmpty(values: Array<string | undefined>): string {
  for (const value of values) {
    const trimmed = value?.trim()
    if (trimmed) return trimmed
  }

  return 'No change explanation available.'
}
