import { describe, expect, it } from 'vitest'

import type {
  DailyEntry,
  RiskIntelSummaryPayload,
  SearchEvidencePayload,
  TickerAnalysisData,
} from '../types'
import type { ActionChangeFeedResult } from './actionChangeFeed'
import type { SectorMoodResult } from './sectorMood'
import type { TodayPriorityQueueResult } from './todayPriorityQueue'
import {
  buildDashboardNewsDeskViewModel,
  buildMarketMoveItems,
  marketRegimeLabel,
} from './newsDesk'

describe('newsDesk view model', () => {
  it('translates internal market regime terms to plain Korean', () => {
    expect(marketRegimeLabel('risk_on')).toBe('위험자산 선호')
    expect(marketRegimeLabel('risk_off')).toBe('안전자산 선호')
    expect(marketRegimeLabel('neutral')).toBe('중립')
    expect(marketRegimeLabel('reflation')).toBe('경기민감 자산 선호')
    expect(marketRegimeLabel('defensive_bias')).toBe('방어적 시장')
    expect(marketRegimeLabel(undefined)).toBe('확인 필요')
    expect(marketRegimeLabel('unknown')).toBe('확인 필요')
  })

  it('builds market overview and macro/real-asset move items in display order', () => {
    const moves = buildMarketMoveItems(buildDay())

    expect(moves.map((item) => item.label)).toEqual([
      'S&P 500',
      '유가 WTI',
      '금',
      '달러',
      '미국 10년 금리',
      '구리',
    ])
    expect(moves.find((item) => item.id === 'real-asset-oil-wti')).toMatchObject({
      value: '$78.12',
      change: '+1.4%',
      directionLabel: '상승',
    })
    expect(moves.find((item) => item.id === 'real-asset-gold')).toMatchObject({
      value: '$2,410',
      change: '-0.2%',
      directionLabel: '하락',
    })
    expect(moves.find((item) => item.id === 'real-asset-copper')).toMatchObject({
      change: '0.0%',
      directionLabel: '안정',
    })
  })

  it('uses Korean direction labels for real-asset changes instead of color alone', () => {
    const moves = buildMarketMoveItems({
      date: '2026-05-28',
      market_overview: [],
      macro_context: {
        oil_wti: { price: '$78.12', change: '+1.4%' },
        gold: { price: '$2,410', change: '-0.2%' },
        dxy: { level: '104.2', change: '0.0%' },
        us10y: { level: '4.41%', change: 'flat' },
        copper: { price: '$4.72' },
      },
      market_regime: null,
      tickers: [],
    })

    expect(moves.find((item) => item.id === 'real-asset-oil-wti')?.directionLabel).toBe('상승')
    expect(moves.find((item) => item.id === 'real-asset-gold')?.directionLabel).toBe('하락')
    expect(moves.find((item) => item.id === 'macro-dollar')?.directionLabel).toBe('안정')
    expect(moves.find((item) => item.id === 'macro-us10y')?.directionLabel).toBe('혼조')
    expect(moves.find((item) => item.id === 'real-asset-copper')?.directionLabel).toBe('확인 필요')
  })

  it('keeps present macro metrics visible when price and level are missing', () => {
    const moves = buildMarketMoveItems({
      date: '2026-05-28',
      market_overview: [],
      macro_context: {
        oil_wti: {},
      },
      market_regime: null,
      tickers: [],
    })

    expect(moves.find((item) => item.id === 'real-asset-oil-wti')).toMatchObject({
      label: '유가 WTI',
      value: '확인 필요',
      directionLabel: '확인 필요',
    })
  })

  it('does not promote missing real-asset values into the news desk feed', () => {
    const result = buildDashboardNewsDeskViewModel({
      day: {
        date: '2026-05-28',
        market_overview: [],
        macro_context: {
          oil_wti: {},
        },
        market_regime: null,
        tickers: [],
      },
      previousDay: null,
    })

    expect(result.marketMoves.find((item) => item.id === 'real-asset-oil-wti')).toMatchObject({
      label: '유가 WTI',
      value: '확인 필요',
      directionLabel: '확인 필요',
    })
    expect(result.feedItems.map((item) => item.id)).not.toContain('market-move-real-asset-oil-wti')
  })

  it('renders generated macro events that only provide event_type and summary_ko', () => {
    const result = buildDashboardNewsDeskViewModel({
      day: {
        date: '2026-05-28',
        market_overview: [],
        macro_context: {
          macro_events: [
            {
              event_type: 'middle_east_escalation',
              severity: 'high',
              summary_ko: '중동 확전 우려로 위험자산 선호가 약해질 수 있습니다.',
              affected_sectors: ['Energy'],
            },
          ],
        },
        market_regime: null,
        tickers: [],
      } as unknown as DailyEntry,
      previousDay: null,
    })

    expect(result.feedItems[0]).toMatchObject({
      id: 'macro-middle-east-escalation',
      title: '중동 확전 리스크',
      whyItMatters: '중동 확전 우려로 위험자산 선호가 약해질 수 있습니다.',
      affectedLabel: 'Energy',
      tone: 'warning',
    })
  })

  it('keeps macro feed rendering stable when generated event identity fields are absent', () => {
    const result = buildDashboardNewsDeskViewModel({
      day: {
        date: '2026-05-28',
        market_overview: [],
        macro_context: {
          macro_events: [
            {
              summary_ko: '시장 전반 리스크를 확인해야 합니다.',
            },
          ],
        },
        market_regime: null,
        tickers: [],
      } as unknown as DailyEntry,
      previousDay: null,
    })

    expect(result.feedItems[0]).toMatchObject({
      id: 'macro-시장-이벤트',
      title: '시장 이벤트',
      whyItMatters: '시장 전반 리스크를 확인해야 합니다.',
    })
  })

  it('builds deterministic headlines, feed items, and impact lists without changing source data', () => {
    const day = buildDay()
    const sourceSnapshot = JSON.stringify(day)

    const result = buildDashboardNewsDeskViewModel({
      day,
      previousDay: null,
      sectorMood: buildSectorMood(),
      actionChangeFeed: buildActionFeed(),
      todayPriorityQueue: buildPriorityQueue(),
      riskIntelSummary: buildRiskIntelSummary(),
      searchEvidence: buildSearchEvidence(),
      qualityLoop: {
        warnings: ['priority_evidence_not_refreshed'],
        evidence_quality: {
          priority_not_refreshed_count: 1,
          provider_issue_status: 'ok',
        },
      },
    })

    expect(JSON.stringify(day)).toBe(sourceSnapshot)
    expect(result.headlines).toHaveLength(3)
    expect(result.headlines.some((headline) => headline.text.includes('위험자산 선호'))).toBe(true)
    expect(result.marketMoves.some((item) => item.label === '유가 WTI')).toBe(true)
    expect(result.feedItems.map((item) => item.id)).toEqual([
      'risk-intel-supply-chain',
      'evidence-refresh-needed',
      'macro-cpi',
      'action-change-AMD',
      'ticker-news-AMD-0',
      'market-move-real-asset-oil-wti',
    ])
    expect(result.impacts.sectors[0]).toMatchObject({ label: '반도체', tone: 'positive' })
    expect(result.impacts.tickers[0]).toMatchObject({ ticker: 'AMD', label: '오늘 우선 확인' })
  })

  it('keeps evidence refresh operations out of the headline action sentence', () => {
    const result = buildDashboardNewsDeskViewModel({
      day: buildDay(),
      previousDay: null,
      todayPriorityQueue: buildPriorityQueue(),
      searchEvidence: buildSearchEvidence(),
      qualityLoop: {
        warnings: ['priority_evidence_not_refreshed'],
        evidence_quality: {
          priority_not_refreshed_count: 1,
          provider_issue_status: 'ok',
        },
      },
    })

    expect(result.states.hasEvidenceWarning).toBe(true)
    expect(result.feedItems.map((item) => item.id)).toContain('evidence-refresh-needed')
    expect(result.headlines.map((headline) => headline.text).join(' ')).not.toContain('근거 갱신')
    expect(result.headlines.find((headline) => headline.id === 'headline-action')).toMatchObject({
      text: 'AMD를 오늘 우선 확인하세요.',
      tone: 'info',
    })
  })

  it('does not create evidence warnings from stale quality-loop telemetry alone', () => {
    const result = buildDashboardNewsDeskViewModel({
      day: buildDay(),
      previousDay: null,
      searchEvidence: {
        schema_version: 1,
        date: '2026-05-28',
        by_ticker: {
          AMD: {
            evidence_status: 'covered',
            priority_for_refresh: true,
            priority_refresh_reasons: [],
          },
        },
        run_summary: {
          provider_error_count: 0,
        },
      },
      qualityLoop: {
        warnings: ['priority_evidence_not_refreshed'],
        evidence_quality: {
          priority_not_refreshed_count: 3,
        },
      },
    })

    expect(result.feedItems.map((item) => item.id)).not.toContain('evidence-refresh-needed')
    expect(result.states.hasEvidenceWarning).toBe(false)
  })

  it('does not count covered priority refresh candidates without gap reasons as evidence warnings', () => {
    const result = buildDashboardNewsDeskViewModel({
      day: buildDay(),
      previousDay: null,
      searchEvidence: {
        schema_version: 1,
        date: '2026-05-28',
        by_ticker: {
          AMD: {
            evidence_status: 'covered',
            priority_for_refresh: true,
          },
        },
        run_summary: {
          provider_error_count: 0,
        },
      },
    })

    expect(result.feedItems.map((item) => item.id)).not.toContain('evidence-refresh-needed')
    expect(result.states.hasEvidenceWarning).toBe(false)
  })

  it('does not create evidence warnings from provider errors without current ticker warning entries', () => {
    const result = buildDashboardNewsDeskViewModel({
      day: buildDay(),
      previousDay: null,
      searchEvidence: {
        schema_version: 1,
        date: '2026-05-28',
        by_ticker: {
          AMD: {
            evidence_status: 'covered',
            priority_for_refresh: false,
          },
        },
        run_summary: {
          provider_error_count: 2,
        },
      },
      qualityLoop: {
        warnings: ['priority_evidence_provider_error'],
      },
    })

    expect(result.feedItems.map((item) => item.id)).not.toContain('evidence-refresh-needed')
    expect(result.states.hasEvidenceWarning).toBe(false)
  })

  it('does not count non-priority not-refreshed evidence rows as warning headlines', () => {
    const result = buildDashboardNewsDeskViewModel({
      day: buildDay(),
      previousDay: null,
      searchEvidence: {
        schema_version: 1,
        date: '2026-05-28',
        by_ticker: {
          AMD: {
            evidence_status: 'not_refreshed',
            priority_for_refresh: false,
            priority_refresh_reasons: ['not_refreshed'],
          },
        },
        run_summary: {
          provider_error_count: 0,
        },
      },
    })

    expect(result.feedItems.map((item) => item.id)).not.toContain('evidence-refresh-needed')
    expect(result.states.hasEvidenceWarning).toBe(false)
  })

  it('returns calm empty and partial-data state when no feed candidate exists', () => {
    const result = buildDashboardNewsDeskViewModel({
      day: {
        date: '2026-05-28',
        market_overview: [],
        macro_context: null,
        market_regime: null,
        tickers: [],
      },
      previousDay: null,
      sectorMood: {
        hasSectorData: false,
        focus: [],
        watch: [],
        neutral: [],
        insights: [],
        emptyReason: 'no sector data',
      },
    })

    expect(result.feedItems).toEqual([])
    expect(result.empty.title).toBe('오늘 크게 달라진 시장 이슈는 없습니다.')
    expect(result.empty.description).toBe('시장 변화와 점검 큐는 계속 확인할 수 있습니다.')
    expect(result.states.hasPartialData).toBe(true)
  })
})

function buildDay(): DailyEntry {
  return {
    date: '2026-05-28',
    market_overview: [
      {
        label: 'S&P 500',
        symbol: 'SPY',
        price: '5,920',
        change: '+0.8%',
      },
    ],
    market_regime: {
      regime: 'risk_on',
      confidence: 72,
      drivers: {
        vix: 'VIX 안정',
        breadth: '상승 확산은 혼조',
      },
      implication: '성장주와 경기민감 섹터 우선 확인',
      assessed_at: '2026-05-28T00:00:00Z',
    },
    macro_context: {
      oil_wti: { price: '$78.12', change: '+1.4%' },
      gold: { price: '$2,410', change: '-0.2%' },
      dxy: { level: '104.2', change: '+0.1%' },
      us10y: { level: '4.41%', change: '-3bp' },
      copper: { price: '$4.72', change: '0.0%' },
      macro_events: [
        {
          type: 'macro',
          event_code: 'CPI',
          label: 'CPI Consumer Inflation',
          date: '2026-05-29',
          days_until: '1',
          severity: 'high',
          summary_ko: '물가 발표 후 금리 민감주 변동성 확인',
          affected_sectors: ['Technology', 'Industrials'],
        },
      ],
    },
    tickers: [
      buildTicker('AMD', 'Advanced Micro Devices', 'Semiconductors', 'buy'),
      buildTicker('XOM', 'Exxon Mobil', 'Energy', 'watch'),
    ],
  }
}

function buildTicker(
  ticker: string,
  name: string,
  sector: string,
  action: 'buy' | 'watch' | 'avoid',
): TickerAnalysisData {
  return {
    ticker,
    name,
    date: '2026-05-28',
    summary: `${ticker} summary`,
    key_news: ticker === 'AMD' ? ['AI 서버 수요 기대가 다시 부각되었습니다.'] : [],
    news_references: [],
    financial_highlights: [],
    risks_or_watchpoints: [],
    signal_or_takeaway: `${ticker} signal`,
    data_snapshot: {
      Sector: sector,
      'Daily Change': ticker === 'AMD' ? '+2.1%' : '+0.4%',
    },
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
      relative_volume: '1.3',
      gap_percent: 'N/A',
      price_vs_sma50: 'N/A',
      price_vs_sma200: 'N/A',
      week52_position: 'N/A',
      rs_vs_spy: 'N/A',
      rs_vs_sector_etf: 'N/A',
    },
    quarterly_financials: [],
    upcoming_events: [],
    news_tone: { label: action === 'avoid' ? 'bearish' : 'bullish', score: 0.6 },
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
      conviction: action === 'buy' ? 82 : 56,
      reason: 'test decision',
      valid_until: '2026-06-01',
      factors: {},
    },
  }
}

function buildSectorMood(): SectorMoodResult {
  return {
    hasSectorData: true,
    focus: [
      {
        sector: 'Semiconductors',
        sectorLabel: '반도체',
        tickerCount: 1,
        classification: 'focus',
        fitLabel: '정합 높음',
        averageDailyChange: 2.1,
        positiveTickerRatio: 1,
        topGainer: { ticker: 'AMD', action: 'buy', conviction: 82, dailyChange: 2.1 },
        topLoser: null,
        representativeTickers: [{ ticker: 'AMD', action: 'buy', conviction: 82, dailyChange: 2.1 }],
        priceFlowScore: 12,
        regimeFitScore: 10,
        tickerSignalScore: 10,
        eventExposureScore: 0,
        score: 32,
        macroEvidence: [],
        rationale: '위험자산 선호 환경에서 반도체 강세',
      },
    ],
    watch: [],
    neutral: [],
    insights: [],
  }
}

function buildActionFeed(): ActionChangeFeedResult {
  return {
    currentDate: '2026-05-28',
    previousDate: '2026-05-27',
    hasPreviousDay: true,
    entries: [
      {
        id: 'action-change-AMD',
        type: 'conviction_change',
        tone: 'positive',
        ticker: 'AMD',
        name: 'Advanced Micro Devices',
        sector: 'Semiconductors',
        previousConviction: 70,
        currentConviction: 82,
        convictionDelta: 12,
        addedRisks: [],
        primaryLabel: '확신도 상승',
        secondaryLabel: '+12pt',
        summary: 'AMD 확신도가 전일 대비 상승했습니다.',
      },
    ],
  }
}

function buildPriorityQueue(): TodayPriorityQueueResult {
  return {
    asOf: '2026-05-28',
    evidenceHealthLabel: '근거 커버리지 80%',
    qualityWarnings: ['priority_evidence_not_refreshed'],
    emptyLabel: '오늘 별도 우선 점검 종목 없음',
    items: [
      {
        id: 'today-priority-AMD',
        ticker: 'AMD',
        name: 'Advanced Micro Devices',
        officialAction: 'BUY',
        priorityScore: 91,
        priorityLabel: 'Risk and opportunity review',
        tone: 'negative',
        riskLevel: 'high',
        riskLabel: 'Risk high',
        opportunityLevel: 'high',
        opportunityLabel: 'Opportunity high',
        evidenceStatus: 'not_refreshed',
        evidenceLabel: 'Evidence refresh needed',
        reasons: ['Risk intelligence alert'],
        nextCheck: '근거 갱신을 먼저 확인하세요.',
        destination: '/ticker/AMD',
      },
    ],
  }
}

function buildRiskIntelSummary(): RiskIntelSummaryPayload {
  return {
    schema_version: '1',
    as_of: '2026-05-28',
    status: 'ok',
    cards: [
      {
        id: 'supply-chain',
        alert_level: 'alert',
        alert_level_label_ko: '경고',
        title_ko: '공급망 리스크 확인 필요',
        summary_ko: '반도체 공급망 이슈가 AMD에 영향을 줄 수 있습니다.',
        affected_sectors: ['Semiconductors'],
        affected_tickers: [
          {
            ticker: 'AMD',
            exposure_type: 'watchlist',
            exposure_label_ko: '관찰 종목',
            is_holding: false,
          },
        ],
        evidence_counts: {},
        top_evidence_refs: [],
        rationale_ko: '뉴스 영향 가능성',
      },
    ],
    counts: { cards: 1, alert_paths: 0 },
    source_tier_status: {},
    empty_states: { ko: '' },
    generation: { run_id: 'risk-run-1' },
    derived_from_graph_run_id: 'graph-run-1',
  }
}

function buildSearchEvidence(): SearchEvidencePayload {
  return {
    schema_version: 1,
    date: '2026-05-28',
    by_ticker: {
      AMD: {
        evidence_status: 'not_refreshed',
        priority_for_refresh: true,
        priority_refresh_reasons: ['risk_alert'],
      },
    },
    run_summary: {
      provider_error_count: 0,
    },
  }
}
