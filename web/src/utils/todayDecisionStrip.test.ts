import { describe, expect, it } from 'vitest'

import type { DailyEntry, TickerAnalysisData } from '../types'
import { buildTodayDecisionStrip, classifyDecisionQuality } from './todayDecisionStrip'

function makeDay(date: string, tickers: TickerAnalysisData[]): DailyEntry {
  return {
    date,
    market_overview: [],
    tickers,
  } as DailyEntry
}

function makeTicker({
  ticker,
  name = `${ticker} Inc.`,
  sector = 'Technology',
  action = 'watch',
  conviction = 50,
  qualityScore,
  confidencePenalty,
  wouldCapAction = false,
  evidenceCoverage,
  evidenceConsistency,
  risks = [],
}: {
  ticker: string
  name?: string
  sector?: string
  action?: 'buy' | 'watch' | 'avoid'
  conviction?: number
  qualityScore?: number
  confidencePenalty?: number
  wouldCapAction?: boolean
  evidenceCoverage?: number
  evidenceConsistency?: number
  risks?: string[]
}): TickerAnalysisData {
  return {
    ticker,
    name,
    date: '2026-05-01',
    summary: `${ticker} summary`,
    key_news: [],
    news_references: [],
    financial_highlights: [],
    risks_or_watchpoints: risks,
    signal_or_takeaway: `${ticker} signal`,
    data_snapshot: { Sector: sector },
    fundamentals: {},
    earnings_setup: {
      forward_eps: 'N/A',
      ttm_eps: 'N/A',
      forward_vs_ttm: 'N/A',
      earnings_growth: 'N/A',
      latest_estimated_eps: 'N/A',
      latest_surprise_pct: 'N/A',
      latest_beat_miss: 'N/A',
      next_earnings_event: 'N/A',
    },
    price_action: {
      atr_14d: 'N/A',
      atr_percent: 'N/A',
      relative_volume: 'N/A',
      gap_percent: 'N/A',
      price_vs_sma50: 'N/A',
      price_vs_sma200: 'N/A',
      week52_position: 'N/A',
      rs_vs_spy: 'N/A',
      rs_vs_sector_etf: 'N/A',
    },
    quarterly_financials: [],
    upcoming_events: [],
    news_tone: { label: 'neutral', score: 0 },
    trade_frame: {
      bull_scenario: 'Bull case',
      base_scenario: 'Base case',
      bear_scenario: 'Bear case',
      invalidation_price: 'N/A',
      watch_period: 'N/A',
    },
    period_changes: {},
    sec_filing_tags: [],
    sec_filings: [],
    decision: {
      action,
      conviction,
      reason: `${ticker} decision reason`,
      valid_until: '2026-05-10',
      factors: {},
      confidence_meta:
        qualityScore === undefined &&
        confidencePenalty === undefined &&
        evidenceCoverage === undefined &&
        evidenceConsistency === undefined &&
        !wouldCapAction
          ? undefined
          : {
              data_quality_score: qualityScore,
              confidence_penalty: confidencePenalty,
              evidence_coverage: evidenceCoverage,
              evidence_consistency: evidenceConsistency,
              data_quality_gate: {
                would_cap_action: wouldCapAction,
                max_action_if_enforced: 'watch',
              },
            },
    },
  } as TickerAnalysisData
}

describe('classifyDecisionQuality', () => {
  it('classifies high, watch, low, and unknown quality', () => {
    expect(classifyDecisionQuality(makeTicker({ ticker: 'HIGH', qualityScore: 0.86 }))).toMatchObject({
      label: 'high quality',
      score: 0.86,
      className: 'today-decision-quality-high',
    })
    expect(classifyDecisionQuality(makeTicker({ ticker: 'WATCH', qualityScore: 0.7 }))).toMatchObject({
      label: 'watch quality',
      score: 0.7,
      className: 'today-decision-quality-watch',
    })
    expect(classifyDecisionQuality(makeTicker({ ticker: 'LOW', qualityScore: 0.52 }))).toMatchObject({
      label: 'low quality',
      score: 0.52,
      className: 'today-decision-quality-low',
    })
    expect(classifyDecisionQuality(makeTicker({ ticker: 'UNK' }))).toMatchObject({
      label: 'unknown',
      score: null,
      className: 'today-decision-quality-unknown',
    })
  })
})

describe('buildTodayDecisionStrip', () => {
  it('ranks quality gates above action changes', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'ALAB', action: 'watch', conviction: 52 }),
      makeTicker({ ticker: 'FLNC', action: 'watch', conviction: 55 }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'ALAB', action: 'buy', conviction: 72, qualityScore: 0.9 }),
      makeTicker({
        ticker: 'FLNC',
        action: 'buy',
        conviction: 65,
        qualityScore: 0.52,
        wouldCapAction: true,
        evidenceCoverage: 0.44,
      }),
    ])

    const strip = buildTodayDecisionStrip(current, previous)

    expect(strip).toMatchObject({
      currentDate: '2026-05-01',
      previousDate: '2026-04-29',
    })
    expect(strip.entries.map((entry) => entry.ticker)).toEqual(['FLNC', 'ALAB'])
    expect(strip.entries[0]).toMatchObject({
      kind: 'quality_gate',
      categoryLabel: 'Quality gate',
      qualityLabel: 'low quality',
      title: 'FLNC BUY capped',
      metricLabel: 'cap to WATCH',
    })
  })

  it('caps entries at five and deduplicates each ticker by highest-ranked item', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'A', action: 'watch', conviction: 50 }),
      makeTicker({ ticker: 'B', action: 'watch', conviction: 50 }),
      makeTicker({ ticker: 'C', action: 'watch', conviction: 50 }),
      makeTicker({ ticker: 'D', action: 'watch', conviction: 50 }),
      makeTicker({ ticker: 'E', action: 'watch', conviction: 50 }),
      makeTicker({ ticker: 'F', action: 'watch', conviction: 50 }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'A', action: 'buy', conviction: 90, qualityScore: 0.9, risks: ['new A risk'] }),
      makeTicker({ ticker: 'B', action: 'buy', conviction: 80, qualityScore: 0.9 }),
      makeTicker({ ticker: 'C', action: 'buy', conviction: 70, qualityScore: 0.9 }),
      makeTicker({ ticker: 'D', action: 'buy', conviction: 60, qualityScore: 0.9 }),
      makeTicker({ ticker: 'E', action: 'buy', conviction: 55, qualityScore: 0.9 }),
      makeTicker({ ticker: 'F', action: 'buy', conviction: 54, qualityScore: 0.9 }),
    ])

    const strip = buildTodayDecisionStrip(current, previous)

    expect(strip.entries).toHaveLength(5)
    expect(new Set(strip.entries.map((entry) => entry.ticker)).size).toBe(5)
    expect(strip.entries.map((entry) => entry.ticker)).toEqual(['A', 'B', 'C', 'D', 'E'])
  })

  it('uses unknown when confidence metadata is absent', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'CAT', action: 'buy', conviction: 72 }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'CAT', action: 'watch', conviction: 63 }),
    ])

    const strip = buildTodayDecisionStrip(current, previous)

    expect(strip.entries[0]).toMatchObject({
      ticker: 'CAT',
      qualityLabel: 'unknown',
      qualityScore: null,
      qualityDetail: 'quality unknown',
    })
  })
})
