import type { DailyEntry, TickerAnalysisData, TickerDecisionData } from '../types'
import {
  buildActionChangeFeed,
  type ActionChangeFeedEntry,
  type ActionChangeFeedResult,
} from './actionChangeFeed'
import { buildSearchEvidenceBadge, type SearchEvidenceBadgeData } from './searchEvidenceBadge'

export type TodayDecisionKind =
  | 'quality_gate'
  | 'action_change'
  | 'conviction_move'
  | 'risk_added'
  | 'new_ticker'

export type TodayDecisionQualityLabel =
  | 'high quality'
  | 'watch quality'
  | 'low quality'
  | 'unknown'

export type TodayDecisionStance = 'positive' | 'negative' | 'caution' | 'neutral' | 'info'

export interface TodayDecisionQuality {
  label: TodayDecisionQualityLabel
  score: number | null
  className: string
  detail: string
  hasGate: boolean
  penalty: number | null
}

export interface TodayDecisionStripEntry {
  id: string
  kind: TodayDecisionKind
  ticker: string
  name: string
  sector: string
  categoryLabel: string
  title: string
  supportingLine: string
  qualityLabel: TodayDecisionQualityLabel
  qualityScore: number | null
  qualityDetail: string
  qualityClassName: string
  metricLabel: string | null
  evidenceBadge?: SearchEvidenceBadgeData
  stance: TodayDecisionStance
  sourceEntryId?: string
  rankScore: number
  convictionRank: number
}

export interface TodayDecisionStripResult {
  currentDate: string
  previousDate: string | null
  entries: TodayDecisionStripEntry[]
}

export interface BuildTodayDecisionStripOptions {
  limit?: number
  feed?: ActionChangeFeedResult
}

const DEFAULT_LIMIT = 5

const ACTION_LABELS: Record<TickerDecisionData['action'], string> = {
  buy: 'BUY',
  watch: 'WATCH',
  avoid: 'AVOID',
}

const KIND_RANK: Record<TodayDecisionKind, number> = {
  quality_gate: 0,
  action_change: 1,
  conviction_move: 2,
  risk_added: 3,
  new_ticker: 4,
}

export function buildTodayDecisionStrip(
  currentDay: DailyEntry,
  previousDay: DailyEntry | null | undefined,
  options: BuildTodayDecisionStripOptions = {},
): TodayDecisionStripResult {
  const limit = resolveLimit(options.limit)
  const feed = options.feed ?? buildActionChangeFeed(currentDay, previousDay)
  const currentByTicker = new Map(
    currentDay.tickers.map((ticker) => [normalizeTicker(ticker.ticker), ticker]),
  )
  const candidates = [
    ...currentDay.tickers
      .map(createQualityGateEntry)
      .filter((entry): entry is TodayDecisionStripEntry => entry !== null),
    ...feed.entries
      .map((entry) => createFeedEntry(entry, currentByTicker.get(normalizeTicker(entry.ticker))))
      .filter((entry): entry is TodayDecisionStripEntry => entry !== null),
  ].sort(compareEntries)

  const deduped = new Map<string, TodayDecisionStripEntry>()
  for (const entry of candidates) {
    if (!deduped.has(entry.ticker)) {
      deduped.set(entry.ticker, entry)
    }
  }

  return {
    currentDate: currentDay.date,
    previousDate: feed.previousDate,
    entries: Array.from(deduped.values()).slice(0, limit),
  }
}

export function classifyDecisionQuality(ticker: TickerAnalysisData): TodayDecisionQuality {
  const meta = ticker.decision?.confidence_meta
  const score = normalizeScore(meta?.data_quality_score ?? meta?.data_quality)
  const penalty = normalizeScore(meta?.confidence_penalty)
  const hasGate = meta?.data_quality_gate?.would_cap_action === true

  if (score === null) {
    return {
      label: 'unknown',
      score: null,
      className: 'today-decision-quality-unknown',
      detail: 'quality unknown',
      hasGate,
      penalty,
    }
  }

  if (score < 0.6) {
    return {
      label: 'low quality',
      score,
      className: 'today-decision-quality-low',
      detail: `quality ${score.toFixed(2)}`,
      hasGate,
      penalty,
    }
  }

  if (score < 0.8) {
    return {
      label: 'watch quality',
      score,
      className: 'today-decision-quality-watch',
      detail: `quality ${score.toFixed(2)}`,
      hasGate,
      penalty,
    }
  }

  return {
    label: 'high quality',
    score,
    className: 'today-decision-quality-high',
    detail: `quality ${score.toFixed(2)}`,
    hasGate,
    penalty,
  }
}

function createQualityGateEntry(ticker: TickerAnalysisData): TodayDecisionStripEntry | null {
  const quality = classifyDecisionQuality(ticker)
  const evidence = buildSearchEvidenceBadge(ticker)
  const action = ticker.decision?.action
  const scoreTriggersGate = quality.score !== null && quality.score < 0.6
  const penaltyTriggersGate = quality.penalty !== null && quality.penalty < 0
  const searchTriggersGate = evidence.wouldCapAction

  if (!quality.hasGate && !scoreTriggersGate && !penaltyTriggersGate && !searchTriggersGate) {
    return null
  }

  const normalizedTicker = normalizeTicker(ticker.ticker)
  const maxAction = ticker.decision?.confidence_meta?.data_quality_gate?.max_action_if_enforced
  const capLabel = maxAction ? `cap to ${String(maxAction).toUpperCase()}` : 'quality gate'
  const isSearchOnlyGate = searchTriggersGate && !quality.hasGate && !scoreTriggersGate && !penaltyTriggersGate

  return {
    id: `quality_gate-${normalizedTicker}`,
    kind: 'quality_gate',
    ticker: normalizedTicker,
    name: ticker.name,
    sector: ticker.data_snapshot?.Sector ?? 'Unknown',
    categoryLabel: isSearchOnlyGate ? 'Evidence gate' : 'Quality gate',
    title: action
      ? isSearchOnlyGate
        ? `${normalizedTicker} evidence gate`
        : `${normalizedTicker} ${ACTION_LABELS[action]} capped`
      : isSearchOnlyGate
        ? `${normalizedTicker} evidence gate`
        : `${normalizedTicker} quality gate`,
    supportingLine: supportingQualityLine(ticker, capLabel),
    qualityLabel: quality.label,
    qualityScore: quality.score,
    qualityDetail: quality.detail,
    qualityClassName: quality.className,
    metricLabel: isSearchOnlyGate ? 'evidence gate' : capLabel,
    evidenceBadge: evidence,
    stance: 'caution',
    rankScore: Math.min(quality.score ?? 1, evidence.score ?? 1),
    convictionRank: numericConviction(ticker) ?? -1,
  }
}

function createFeedEntry(
  feedEntry: ActionChangeFeedEntry,
  ticker: TickerAnalysisData | undefined,
): TodayDecisionStripEntry | null {
  if (!ticker) return null

  const quality = classifyDecisionQuality(ticker)
  const evidence = buildSearchEvidenceBadge(ticker)
  const normalizedTicker = normalizeTicker(feedEntry.ticker)
  const kind = kindFromFeedEntry(feedEntry)

  return {
    id: `${kind}-${normalizedTicker}`,
    kind,
    ticker: normalizedTicker,
    name: feedEntry.name,
    sector: feedEntry.sector,
    categoryLabel: categoryLabelFor(feedEntry),
    title: `${normalizedTicker} ${feedEntry.primaryLabel}`,
    supportingLine: supportingLineForFeed(feedEntry),
    qualityLabel: quality.label,
    qualityScore: quality.score,
    qualityDetail: quality.detail,
    qualityClassName: quality.className,
    metricLabel: metricLabelForFeed(feedEntry),
    evidenceBadge: evidence,
    stance: feedEntry.tone,
    sourceEntryId: feedEntry.id,
    rankScore: quality.score ?? 1,
    convictionRank: feedEntry.currentConviction ?? -1,
  }
}

function kindFromFeedEntry(feedEntry: ActionChangeFeedEntry): TodayDecisionKind {
  if (feedEntry.type === 'conviction_change') return 'conviction_move'
  return feedEntry.type
}

function categoryLabelFor(feedEntry: ActionChangeFeedEntry): string {
  if (feedEntry.type === 'action_change') {
    if (feedEntry.currentAction === 'buy') return 'Top action'
    if (feedEntry.previousAction === 'buy' || feedEntry.currentAction === 'avoid') return 'Risk alert'
    return 'Action change'
  }

  if (feedEntry.type === 'conviction_change') return 'Conviction move'
  if (feedEntry.type === 'risk_added') return 'New risk'
  return 'New ticker'
}

function supportingLineForFeed(feedEntry: ActionChangeFeedEntry): string {
  if (feedEntry.addedRisks[0]) {
    return `${feedEntry.secondaryLabel} · 리스크 ${feedEntry.addedRisks.length}개`
  }

  return feedEntry.secondaryLabel
}

function metricLabelForFeed(feedEntry: ActionChangeFeedEntry): string | null {
  if (feedEntry.convictionDelta !== null) {
    return `${feedEntry.convictionDelta >= 0 ? '+' : ''}${feedEntry.convictionDelta}p`
  }

  if (feedEntry.addedRisks.length > 0) {
    return `risk x${feedEntry.addedRisks.length}`
  }

  return null
}

function supportingQualityLine(ticker: TickerAnalysisData, fallback: string): string {
  const meta = ticker.decision?.confidence_meta
  const coverage = normalizeScore(meta?.evidence_coverage)
  const consistency = normalizeScore(meta?.evidence_consistency)
  const penalty = normalizeScore(meta?.confidence_penalty)
  const parts = [fallback]

  if (coverage !== null) parts.push(`coverage ${coverage.toFixed(2)}`)
  if (consistency !== null) parts.push(`consistency ${consistency.toFixed(2)}`)
  if (penalty !== null && penalty < 0) parts.push(`penalty ${penalty.toFixed(2)}`)

  return parts.join(' · ')
}

function compareEntries(left: TodayDecisionStripEntry, right: TodayDecisionStripEntry): number {
  const kindDiff = KIND_RANK[left.kind] - KIND_RANK[right.kind]
  if (kindDiff !== 0) return kindDiff

  if (left.kind === 'quality_gate') {
    const qualityDiff = left.rankScore - right.rankScore
    if (qualityDiff !== 0) return qualityDiff
  }

  const deltaDiff = Math.abs(metricDelta(right.metricLabel)) - Math.abs(metricDelta(left.metricLabel))
  if (deltaDiff !== 0) return deltaDiff

  const convictionDiff = right.convictionRank - left.convictionRank
  if (convictionDiff !== 0) return convictionDiff

  return left.ticker.localeCompare(right.ticker)
}

function metricDelta(metric: string | null): number {
  if (!metric) return 0
  const parsed = Number.parseFloat(metric.replace('p', ''))
  return Number.isFinite(parsed) ? parsed : 0
}

function resolveLimit(limit: number | undefined): number {
  if (limit === undefined) return DEFAULT_LIMIT
  return Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : DEFAULT_LIMIT
}

function normalizeScore(value: number | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function normalizeTicker(ticker: string): string {
  return ticker.trim().toUpperCase()
}

function numericConviction(ticker: TickerAnalysisData): number | null {
  const conviction = ticker.decision?.conviction
  return typeof conviction === 'number' && Number.isFinite(conviction) ? conviction : null
}
