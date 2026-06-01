import { describe, expect, it } from 'vitest'

import type {
  DailyEntry,
  QualityReliabilityLoopPayload,
  RiskIntelSummaryPayload,
  SearchEvidencePayload,
  TickerAnalysisData,
} from '../types'
import { buildTodayPriorityQueue } from './todayPriorityQueue'

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
  action = 'watch',
  conviction = 50,
  newsTone = 'neutral',
  relativeVolume = '1.0',
  rsVsSpy = '0%',
  rsVsSector = '0%',
}: {
  ticker: string
  name?: string
  action?: 'buy' | 'watch' | 'avoid'
  conviction?: number
  newsTone?: 'bullish' | 'neutral' | 'bearish'
  relativeVolume?: string
  rsVsSpy?: string
  rsVsSector?: string
}): TickerAnalysisData {
  return {
    ticker,
    name,
    date: '2026-05-21',
    summary: `${ticker} summary`,
    key_news: [],
    news_references: [],
    financial_highlights: [],
    risks_or_watchpoints: [],
    signal_or_takeaway: `${ticker} signal`,
    data_snapshot: {},
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
      relative_volume: relativeVolume,
      gap_percent: 'N/A',
      price_vs_sma50: 'N/A',
      price_vs_sma200: 'N/A',
      week52_position: 'N/A',
      rs_vs_spy: rsVsSpy,
      rs_vs_sector_etf: rsVsSector,
    },
    quarterly_financials: [],
    upcoming_events: [],
    news_tone: { label: newsTone, score: newsTone === 'bullish' ? 1 : 0 },
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
      valid_until: '2026-05-30',
      factors: {},
    },
  } as TickerAnalysisData
}

function makeRiskIntelSummary(ticker: string, title: string): RiskIntelSummaryPayload {
  return {
    schema_version: '1.0.0',
    as_of: '2026-05-21',
    status: 'ok',
    cards: [
      {
        id: `risk-${ticker}`,
        alert_level: 'alert',
        alert_level_label_ko: 'Alert',
        title_ko: title,
        summary_ko: `${ticker} risk summary`,
        affected_sectors: [],
        affected_tickers: [
          {
            ticker,
            exposure_type: 'watchlist',
            exposure_label_ko: '관심',
            is_holding: false,
          },
        ],
        evidence_counts: {},
        top_evidence_refs: [],
        rationale_ko: `${ticker} rationale`,
      },
    ],
    counts: {
      cards: 1,
      alert_paths: 1,
    },
    source_tier_status: {},
    empty_states: {
      ko: '',
    },
    generation: {
      run_id: 'risk-run',
    },
    derived_from_graph_run_id: 'risk-run',
  }
}

function makeSearchEvidence(byTicker: SearchEvidencePayload['by_ticker']): SearchEvidencePayload {
  return {
    schema_version: 1,
    date: '2026-05-21',
    by_ticker: byTicker,
    run_summary: {
      cache_ttl_hours: 24,
    },
  }
}

function makeQualityLoop(coverageRatio: number): QualityReliabilityLoopPayload {
  return {
    schema_version: 1,
    as_of: '2026-05-21',
    evidence_quality: {
      coverage_ratio: coverageRatio,
    },
  }
}

describe('buildTodayPriorityQueue', () => {
  it('ranks combined risk and opportunity ahead of low-context names', () => {
    const day = makeDay('2026-05-21', [
      makeTicker({
        ticker: 'MSFT',
        action: 'watch',
      }),
      makeTicker({
        ticker: 'amd',
        name: 'Advanced Micro Devices',
        action: 'buy',
        conviction: 74,
        newsTone: 'bullish',
        relativeVolume: '1.7',
        rsVsSpy: '+4.2%',
      }),
    ])

    const result = buildTodayPriorityQueue({
      day,
      riskIntelSummary: makeRiskIntelSummary('AMD', 'AI supply-chain pressure'),
      qualityLoop: makeQualityLoop(0.8),
    })

    expect(result.items.map((item) => item.ticker)).toEqual(['AMD'])
    expect(result.items[0]).toMatchObject({
      ticker: 'AMD',
      name: 'Advanced Micro Devices',
      officialAction: 'BUY',
      riskLevel: 'high',
      riskLabel: 'Risk high',
      opportunityLevel: 'high',
      opportunityLabel: 'Opportunity high',
      priorityLabel: 'Risk and opportunity review',
      nextCheck: '리스크 경로와 보유 영향부터 확인하세요.',
      destination: '/ticker/AMD',
    })
    expect(result.items[0].reasons).toEqual(
      expect.arrayContaining(['AI supply-chain pressure', 'BUY with high conviction']),
    )
  })

  it('creates a not-refreshed evidence priority and ranks it above covered evidence', () => {
    const day = makeDay('2026-05-21', [
      makeTicker({
        ticker: 'KO',
        action: 'avoid',
      }),
      makeTicker({
        ticker: 'cat',
        name: 'Caterpillar',
      }),
    ])
    const searchEvidence = makeSearchEvidence({
      CAT: {
        priority_refresh_reasons: ['not_refreshed'],
      },
      KO: {
        evidence_count: 4,
        evidence_status: 'covered',
      },
    })

    const result = buildTodayPriorityQueue({
      day,
      searchEvidence,
    })

    expect(result.items.map((item) => item.ticker)).toEqual(['CAT', 'KO'])
    expect(result.items[0]).toMatchObject({
      ticker: 'CAT',
      evidenceStatus: 'not_refreshed',
      evidenceLabel: 'Evidence refresh needed',
      priorityLabel: 'Evidence review',
      nextCheck: '근거 부족이 판단을 흔드는지 확인하세요.',
    })
    expect(result.items[0].reasons).toContain('Priority evidence was not refreshed')
  })

  it('uses exact Korean next-check guidance by priority context', () => {
    const highOpportunityNotCovered = buildTodayPriorityQueue({
      day: makeDay('2026-05-21', [
        makeTicker({ ticker: 'ALAB', action: 'buy', conviction: 80 }),
      ]),
    })
    const highOpportunityCovered = buildTodayPriorityQueue({
      day: makeDay('2026-05-21', [
        makeTicker({ ticker: 'NVDA', action: 'buy', conviction: 80 }),
      ]),
      searchEvidence: makeSearchEvidence({
        NVDA: {
          evidence_count: 3,
          evidence_status: 'covered',
        },
      }),
    })
    const defaultReview = buildTodayPriorityQueue({
      day: makeDay('2026-05-21', [
        makeTicker({ ticker: 'KO', action: 'avoid' }),
      ]),
    })

    expect(highOpportunityNotCovered.items[0].nextCheck).toBe('기회는 강하지만 근거 갱신을 먼저 확인하세요.')
    expect(highOpportunityCovered.items[0].nextCheck).toBe('기회 근거와 진입 조건을 확인하세요.')
    expect(defaultReview.items[0].nextCheck).toBe('핵심 논점과 공식 판단을 확인하세요.')
  })

  it('preserves dashboard order when scores are tied', () => {
    const day = makeDay('2026-05-21', [
      makeTicker({ ticker: 'AAA', action: 'buy', conviction: 60 }),
      makeTicker({ ticker: 'BBB', action: 'buy', conviction: 60 }),
      makeTicker({ ticker: 'CCC', action: 'buy', conviction: 60 }),
    ])

    const result = buildTodayPriorityQueue({
      day,
    })

    expect(result.items.map((item) => item.ticker)).toEqual(['AAA', 'BBB', 'CCC'])
  })

  it('returns an empty state when optional artifacts and review signals are missing', () => {
    const day = makeDay('2026-05-21', [
      makeTicker({ ticker: 'KO', action: 'watch' }),
    ])

    const result = buildTodayPriorityQueue({
      day,
    })

    expect(result).toMatchObject({
      items: [],
      asOf: '2026-05-21',
      evidenceHealthLabel: '근거 상태 없음',
      qualityWarnings: [],
      emptyLabel: '오늘 별도 우선 점검 종목 없음',
    })
  })
})
