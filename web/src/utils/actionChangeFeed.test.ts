import { describe, expect, it } from 'vitest'

import type { DailyEntry, TickerAnalysisData } from '../types'
import { buildActionChangeFeed, findPreviousValidDay } from './actionChangeFeed'

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
  action,
  conviction,
  reason = `${ticker} decision reason`,
  risks = [],
  signal = `${ticker} signal`,
  summary = `${ticker} summary`,
}: {
  ticker: string
  name?: string
  sector?: string
  action?: 'buy' | 'watch' | 'avoid'
  conviction?: number
  reason?: string
  risks?: string[]
  signal?: string
  summary?: string
}): TickerAnalysisData {
  return {
    ticker,
    name,
    date: '2026-05-01',
    summary,
    key_news: [],
    news_references: [],
    financial_highlights: [],
    risks_or_watchpoints: risks,
    signal_or_takeaway: signal,
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
    decision: action
      ? {
          action,
          conviction: conviction ?? 50,
          reason,
          valid_until: '2026-05-10',
          factors: {},
        }
      : undefined,
  } as TickerAnalysisData
}

describe('buildActionChangeFeed', () => {
  it('creates an action_change entry for watch to buy', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'ALAB', action: 'watch', conviction: 52 }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'ALAB', action: 'buy', conviction: 72 }),
    ])

    const feed = buildActionChangeFeed(current, previous)

    expect(feed).toMatchObject({
      currentDate: '2026-05-01',
      previousDate: '2026-04-29',
      hasPreviousDay: true,
    })
    expect(feed.entries).toHaveLength(1)
    expect(feed.entries[0]).toMatchObject({
      id: 'action_change-ALAB',
      type: 'action_change',
      tone: 'positive',
      ticker: 'ALAB',
      name: 'ALAB Inc.',
      sector: 'Technology',
      previousAction: 'watch',
      currentAction: 'buy',
      previousConviction: 52,
      currentConviction: 72,
      convictionDelta: 20,
      addedRisks: [],
      primaryLabel: 'WATCH -> BUY',
      secondaryLabel: 'Conviction 52 -> 72 (+20p)',
      summary: 'ALAB decision reason',
    })
  })

  it('creates an action_change entry for buy to watch', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'CAT', action: 'buy', conviction: 70 }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'CAT', action: 'watch', conviction: 61 }),
    ])

    const feed = buildActionChangeFeed(current, previous)

    expect(feed.entries[0]).toMatchObject({
      type: 'action_change',
      tone: 'negative',
      ticker: 'CAT',
      previousAction: 'buy',
      currentAction: 'watch',
      convictionDelta: -9,
      primaryLabel: 'BUY -> WATCH',
    })
  })

  it('creates a conviction_change entry when the absolute delta is at least 10', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'XOM', action: 'watch', conviction: 63 }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'XOM', action: 'watch', conviction: 50 }),
    ])

    const feed = buildActionChangeFeed(current, previous)

    expect(feed.entries[0]).toMatchObject({
      type: 'conviction_change',
      tone: 'caution',
      ticker: 'XOM',
      convictionDelta: -13,
      primaryLabel: '-13p',
      secondaryLabel: 'Conviction 63 -> 50 (-13p)',
    })
  })

  it('does not create a conviction entry below the default threshold', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'AMD', action: 'buy', conviction: 64 }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'AMD', action: 'buy', conviction: 68 }),
    ])

    const feed = buildActionChangeFeed(current, previous)

    expect(feed.entries).toHaveLength(0)
  })

  it('falls back to the default conviction threshold when the option is NaN', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'MSFT', action: 'watch', conviction: 50 }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'MSFT', action: 'watch', conviction: 60 }),
    ])

    const feed = buildActionChangeFeed(current, previous, { convictionDeltaThreshold: Number.NaN })

    expect(feed.entries[0]).toMatchObject({
      type: 'conviction_change',
      ticker: 'MSFT',
      convictionDelta: 10,
    })
  })

  it('falls back to the default conviction threshold when the option is negative', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'ORCL', action: 'watch', conviction: 50 }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'ORCL', action: 'watch', conviction: 55 }),
    ])

    const feed = buildActionChangeFeed(current, previous, { convictionDeltaThreshold: -1 })

    expect(feed.entries).toHaveLength(0)
  })

  it('allows zero as an explicit conviction threshold', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'META', action: 'watch', conviction: 50 }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'META', action: 'watch', conviction: 50 }),
    ])

    const feed = buildActionChangeFeed(current, previous, { convictionDeltaThreshold: 0 })

    expect(feed.entries[0]).toMatchObject({
      type: 'conviction_change',
      ticker: 'META',
      convictionDelta: 0,
      primaryLabel: '+0p',
    })
  })

  it('creates a new_ticker entry for a current ticker that was not in the previous day', () => {
    const previous = makeDay('2026-04-29', [])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'cohr', action: 'watch', conviction: 64 }),
    ])

    const feed = buildActionChangeFeed(current, previous)

    expect(feed.entries[0]).toMatchObject({
      id: 'new_ticker-COHR',
      type: 'new_ticker',
      tone: 'info',
      ticker: 'COHR',
      currentAction: 'watch',
      previousConviction: null,
      currentConviction: 64,
      convictionDelta: null,
      primaryLabel: 'NEW WATCH',
      secondaryLabel: 'Conviction 64',
    })
  })

  it('attaches added risks to a higher-priority action entry', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({
        ticker: 'CAT',
        action: 'buy',
        conviction: 70,
        risks: ['Earnings risk'],
      }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({
        ticker: 'CAT',
        action: 'watch',
        conviction: 61,
        risks: ['Earnings risk', 'Valuation risk'],
      }),
    ])

    const feed = buildActionChangeFeed(current, previous)

    expect(feed.entries).toHaveLength(1)
    expect(feed.entries[0]).toMatchObject({ type: 'action_change', ticker: 'CAT' })
    expect(feed.entries[0].addedRisks).toEqual(['Valuation risk'])
  })

  it('creates risk-only entries after normalizing risk text and preserving display text', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'KO', action: 'watch', conviction: 51, risks: ['Margin risk'] }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({
        ticker: 'KO',
        action: 'watch',
        conviction: 51,
        risks: ['  margin   risk ', '  Input   cost   risk  '],
      }),
    ])

    const feed = buildActionChangeFeed(current, previous)

    expect(feed.entries[0]).toMatchObject({
      type: 'risk_added',
      tone: 'caution',
      ticker: 'KO',
      primaryLabel: 'NEW RISK x1',
      secondaryLabel: 'Conviction 51 -> 51 (+0p)',
      summary: 'KO decision reason',
    })
    expect(feed.entries[0].addedRisks).toEqual(['Input cost risk'])
  })

  it('skips action and conviction comparisons for one-sided missing decisions but still reports added risks', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'MSPREV', risks: [] }),
      makeTicker({ ticker: 'MSCUR', action: 'watch', conviction: 52, risks: [] }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'MSPREV', action: 'buy', conviction: 75, risks: ['New risk'] }),
      makeTicker({ ticker: 'MSCUR', risks: ['Fresh risk'] }),
    ])

    const feed = buildActionChangeFeed(current, previous)

    expect(feed.entries).toHaveLength(2)
    expect(feed.entries.map((entry) => entry.type)).toEqual(['risk_added', 'risk_added'])
    expect(feed.entries).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: 'risk_added',
          ticker: 'MSPREV',
          previousAction: undefined,
          currentAction: 'buy',
          previousConviction: null,
          currentConviction: 75,
          convictionDelta: null,
          addedRisks: ['New risk'],
        }),
        expect.objectContaining({
          type: 'risk_added',
          ticker: 'MSCUR',
          previousAction: 'watch',
          currentAction: undefined,
          previousConviction: 52,
          currentConviction: null,
          convictionDelta: null,
          addedRisks: ['Fresh risk'],
        }),
      ]),
    )
  })

  it('sorts entries by type rank, absolute conviction delta, current conviction, and ticker', () => {
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'ALOW', action: 'watch', conviction: 40 }),
      makeTicker({ ticker: 'ZHIGH', action: 'watch', conviction: 50 }),
      makeTicker({ ticker: 'XOM', action: 'watch', conviction: 63 }),
      makeTicker({ ticker: 'KO', action: 'watch', conviction: 51, risks: [] }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'KO', action: 'watch', conviction: 51, risks: ['Input cost risk'] }),
      makeTicker({ ticker: 'COHR', action: 'watch', conviction: 70 }),
      makeTicker({ ticker: 'XOM', action: 'watch', conviction: 50 }),
      makeTicker({ ticker: 'ALOW', action: 'buy', conviction: 50 }),
      makeTicker({ ticker: 'ZHIGH', action: 'buy', conviction: 60 }),
    ])

    const feed = buildActionChangeFeed(current, previous)

    expect(feed.entries.map((entry) => `${entry.type}:${entry.ticker}`)).toEqual([
      'action_change:ZHIGH',
      'action_change:ALOW',
      'conviction_change:XOM',
      'new_ticker:COHR',
      'risk_added:KO',
    ])
  })

  it('handles a missing previous day without throwing', () => {
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'AAPL', action: 'watch', conviction: 56 }),
    ])

    const feed = buildActionChangeFeed(current, null)

    expect(feed).toMatchObject({
      currentDate: '2026-05-01',
      previousDate: null,
      hasPreviousDay: false,
      entries: [],
    })
  })
})

describe('findPreviousValidDay', () => {
  it('returns the nearest earlier day with ticker data', () => {
    const empty = makeDay('2026-04-28', [])
    const previous = makeDay('2026-04-29', [
      makeTicker({ ticker: 'AAPL', action: 'watch', conviction: 56 }),
    ])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'AAPL', action: 'watch', conviction: 58 }),
    ])

    expect(findPreviousValidDay([empty, previous, current], 2)).toBe(previous)
  })

  it('returns null when there is no earlier valid day', () => {
    const empty = makeDay('2026-04-28', [])
    const current = makeDay('2026-05-01', [
      makeTicker({ ticker: 'AAPL', action: 'watch', conviction: 58 }),
    ])

    expect(findPreviousValidDay([empty, current], 1)).toBeNull()
  })
})
