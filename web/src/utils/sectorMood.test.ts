import { describe, expect, it } from 'vitest'

import type { MacroContext, MarketRegimeData, TickerAnalysisData } from '../types'
import {
  buildMarketMoodSummary,
  deriveSectorMoodInsights,
  formatSectorPercent,
  getSectorLabel,
} from './sectorMood'

const regime: MarketRegimeData = {
  regime: 'risk_on',
  confidence: 78,
  drivers: {
    volatility: 'VIX 안정',
    growth: 'NASDAQ 강세',
  },
  implication: '성장 섹터 우선 확인',
  assessed_at: '2026-04-30',
}

const macroContext: MacroContext = {
  macro_events: [
    {
      type: 'macro',
      date: '2026-04-30',
      days_until: '0',
      label: '성장주 심리 개선',
      affected_sectors: ['Semiconductors'],
      market_bias: 'NASDAQ 강세와 위험 선호 개선',
      summary_ko: '반도체 업종에 긍정적인 성장주 강세 흐름',
      severity: 'medium',
    },
  ],
  upcoming_macro_events: [
    {
      type: 'macro',
      date: '2026-05-01',
      days_until: '1',
      label: '금리 이벤트',
      affected_sectors: ['Utilities'],
      market_bias: '금리 민감 섹터 변동성 부담',
      severity: 'high',
      impact: 'high',
    },
  ],
}

function makeTicker(
  ticker: string,
  sector: string,
  dailyChange: string | undefined,
  action: 'buy' | 'watch' | 'avoid',
  conviction: number,
  factors: Record<string, number> = {},
): TickerAnalysisData {
  return {
    ticker,
    name: ticker,
    date: '2026-04-30',
    summary: `${ticker} 요약`,
    key_news: [],
    news_references: [],
    financial_highlights: [],
    risks_or_watchpoints: [],
    signal_or_takeaway: '섹터 흐름 확인',
    data_snapshot: {
      Sector: sector,
      ...(dailyChange === undefined ? {} : { 'Daily Change': dailyChange }),
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
    news_tone: {
      label: 'neutral',
      score: 0,
    },
    trade_frame: {
      bull_scenario: 'N/A',
      base_scenario: 'N/A',
      bear_scenario: 'N/A',
      invalidation_price: 'N/A',
      watch_period: 'N/A',
    },
    period_changes: {},
    sec_filing_tags: [],
    sec_filings: [],
    decision: {
      action,
      conviction,
      reason: '테스트 판단',
      valid_until: '2026-05-07',
      factors,
    },
  }
}

describe('deriveSectorMoodInsights', () => {
  it('classifies aligned growth sector as focus and lagging sector as watch', () => {
    const result = deriveSectorMoodInsights({
      tickers: [
        makeTicker('NVDA', 'Semiconductors', '+2.4%', 'buy', 88, {
          macro_regime: 1,
          regime_adjustment: 0.8,
          macro_event: 0.6,
        }),
        makeTicker('AMD', 'Semiconductors', '+1.2%', 'buy', 82, {
          macro_regime: 0.8,
          regime_adjustment: 0.6,
          macro_event: 0.5,
        }),
        makeTicker('NEE', 'Utilities', '-0.6%', 'watch', 42, {
          macro_regime: -0.7,
          regime_adjustment: -0.6,
          macro_event: -0.8,
        }),
        makeTicker('DUK', 'Utilities', '-0.4%', 'avoid', 35, {
          macro_regime: -0.8,
          regime_adjustment: -0.7,
          macro_event: -0.8,
        }),
      ],
      marketRegime: regime,
      macroContext,
    })

    expect(result.hasSectorData).toBe(true)
    expect(result.focus.map((sector) => sector.sector)).toContain('Semiconductors')
    expect(result.watch.map((sector) => sector.sector)).toContain('Utilities')
    expect(result.focus.find((sector) => sector.sector === 'Semiconductors')?.representativeTickers.map((ref) => ref.ticker)).toContain('NVDA')
    expect(result.watch.find((sector) => sector.sector === 'Utilities')?.rationale).not.toContain('매도')
  })

  it('does not force classifications for empty input', () => {
    const result = deriveSectorMoodInsights({
      tickers: [],
      marketRegime: regime,
      macroContext,
    })

    expect(result.hasSectorData).toBe(false)
    expect(result.focus).toEqual([])
    expect(result.watch).toEqual([])
    expect(result.emptyReason).toBe('섹터 데이터 부족')
  })

  it('keeps missing daily changes out of displayed percentages', () => {
    const result = deriveSectorMoodInsights({
      tickers: [makeTicker('MSFT', 'Technology', undefined, 'watch', 50)],
      marketRegime: regime,
      macroContext,
    })

    expect(result.insights.find((sector) => sector.sector === 'Technology')?.averageDailyChange).toBeNull()
    expect(formatSectorPercent(null)).toBe('N/A')
  })

  it('keeps trading command words out of rationale when regime implication includes them', () => {
    const unsafeRegime: MarketRegimeData = {
      ...regime,
      implication: '매수 우위와 매도 압박',
    }

    const result = deriveSectorMoodInsights({
      tickers: [
        makeTicker('NVDA', 'Semiconductors', '+2.4%', 'buy', 88, {
          macro_regime: 1,
          regime_adjustment: 0.8,
        }),
      ],
      marketRegime: unsafeRegime,
      macroContext: {},
    })

    expect(result.focus[0]?.rationale).not.toMatch(/매수|매도/)
  })

  it('uses marketRegime for rationale text without falling back to missing mood copy', () => {
    const result = deriveSectorMoodInsights({
      tickers: [
        makeTicker('NVDA', 'Semiconductors', '+2.4%', 'buy', 88, {
          macro_regime: 1,
          regime_adjustment: 0.8,
        }),
      ],
      marketRegime: regime,
      macroContext: {},
    })

    expect(result.focus[0]?.rationale).toContain('risk_on 분위기')
  })

  it('normalizes production-scale decision factors by factor bounds', () => {
    const result = deriveSectorMoodInsights({
      tickers: [
        makeTicker('MOD', 'Technology', '+0.2%', 'watch', 50, {
          macro_event: 1,
          macro_regime: 2,
          regime_adjustment: 5,
        }),
        makeTicker('MAX', 'Energy', '+0.2%', 'watch', 50, {
          macro_event: 6,
          macro_regime: 8,
          regime_adjustment: 15,
        }),
        makeTicker('MIN', 'Utilities', '-0.2%', 'watch', 50, {
          macro_event: -8,
          macro_regime: -6,
          regime_adjustment: -15,
        }),
      ],
      marketRegime: regime,
      macroContext: {},
    })

    const moderate = result.insights.find((sector) => sector.sector === 'Technology')
    const maxish = result.insights.find((sector) => sector.sector === 'Energy')
    const minish = result.insights.find((sector) => sector.sector === 'Utilities')

    expect(moderate?.regimeFitScore).toBeGreaterThan(0.2)
    expect(moderate?.regimeFitScore).toBeLessThan(0.4)
    expect(maxish?.regimeFitScore).toBeCloseTo(1)
    expect(minish?.regimeFitScore).toBeCloseTo(-1)
  })

  it('keeps the lowest scoring watch candidates when more than three qualify', () => {
    const result = deriveSectorMoodInsights({
      tickers: [
        makeTicker('UTIL', 'Utilities', '-0.1%', 'watch', 40, {
          macro_regime: -0.3,
        }),
        makeTicker('REAL', 'Real Estate', '-0.2%', 'watch', 35, {
          macro_regime: -0.5,
        }),
        makeTicker('MATS', 'Materials', '-1.1%', 'avoid', 30, {
          macro_regime: -0.9,
        }),
        makeTicker('ENER', 'Energy', '-1.6%', 'avoid', 25, {
          macro_regime: -1,
        }),
        makeTicker('FIN', 'Financials', '-2.1%', 'avoid', 20, {
          macro_regime: -1,
          regime_adjustment: -1,
        }),
      ],
      marketRegime: regime,
      macroContext: {},
    })

    expect(result.watch.map((sector) => sector.sector)).toEqual(['Financials', 'Energy', 'Materials'])
  })

  it('treats risk appetite improvement as supportive macro evidence', () => {
    const result = deriveSectorMoodInsights({
      tickers: [
        makeTicker('NVDA', 'Semiconductors', '+1.4%', 'buy', 82, {
          macro_regime: 0.6,
          regime_adjustment: 0.5,
        }),
      ],
      marketRegime: regime,
      macroContext: {
        macro_events: [
          {
            type: 'macro',
            date: '2026-04-30',
            days_until: '0',
            label: '위험 선호 개선',
            affected_sectors: ['Semiconductors'],
            market_bias: '위험 선호 개선과 risk appetite improved',
            severity: 'medium',
          },
        ],
      },
    })

    const semiconductors = result.focus.find((sector) => sector.sector === 'Semiconductors')
    expect(semiconductors?.eventExposureScore).toBeGreaterThanOrEqual(0)
    expect(semiconductors?.rationale).not.toBe('매크로 이벤트 노출이 있어 변동성과 상대강도를 확인할 섹터입니다.')
  })

  it('treats weakened risk appetite as bearish macro evidence', () => {
    const result = deriveSectorMoodInsights({
      tickers: [
        makeTicker('NVDA', 'Semiconductors', '+1.4%', 'buy', 82, {
          macro_regime: 0.6,
          regime_adjustment: 0.5,
        }),
      ],
      marketRegime: regime,
      macroContext: {
        macro_events: [
          {
            type: 'macro',
            date: '2026-04-30',
            days_until: '0',
            label: 'Risk appetite fading',
            affected_sectors: ['Semiconductors'],
            market_bias: 'risk appetite weakened amid volatility',
            severity: 'medium',
          },
        ],
      },
    })

    const semiconductors = result.insights.find((sector) => sector.sector === 'Semiconductors')
    expect(semiconductors?.eventExposureScore).toBeLessThan(0)
    expect(semiconductors?.rationale).toBe('매크로 이벤트 노출이 있어 변동성과 상대강도를 확인할 섹터입니다.')
  })

  it('keeps full ticker count when representative tickers are capped', () => {
    const result = deriveSectorMoodInsights({
      tickers: [
        makeTicker('AAPL', 'Technology', '+1.1%', 'buy', 85),
        makeTicker('MSFT', 'Technology', '+0.9%', 'buy', 82),
        makeTicker('GOOGL', 'Technology', '+0.7%', 'watch', 70),
        makeTicker('META', 'Technology', '+0.6%', 'watch', 65),
        makeTicker('ORCL', 'Technology', '+0.4%', 'watch', 60),
      ],
      marketRegime: regime,
      macroContext: {},
    })

    const technology = result.insights.find((sector) => sector.sector === 'Technology')
    expect(technology?.tickerCount).toBe(5)
    expect(technology?.representativeTickers).toHaveLength(4)
  })

  it('maps common sector aliases to Korean labels', () => {
    expect(getSectorLabel('Consumer Defensive')).toBe('필수소비재')
    expect(getSectorLabel('Financial')).toBe('금융')
    expect(getSectorLabel('Financial Services')).toBe('금융')
    expect(getSectorLabel('Communication')).toBe('커뮤니케이션')
    expect(getSectorLabel('Communication Services')).toBe('커뮤니케이션')
  })

  it('matches macro evidence across sector aliases', () => {
    const result = deriveSectorMoodInsights({
      tickers: [
        makeTicker('AMZN', 'Consumer Discretionary', '+0.8%', 'watch', 55),
        makeTicker('JPM', 'Financials', '+0.4%', 'watch', 52),
        makeTicker('PG', 'Consumer Staples', '+0.3%', 'watch', 50),
      ],
      marketRegime: regime,
      macroContext: {
        macro_events: [
          {
            type: 'macro',
            date: '2026-04-30',
            days_until: '0',
            label: '경기소비재 강세',
            affected_sectors: ['Consumer Cyclical'],
            market_bias: '소비 심리 개선',
          },
          {
            type: 'macro',
            date: '2026-04-30',
            days_until: '0',
            label: '금융 여건 개선',
            affected_sectors: ['Financial'],
            market_bias: '신용 환경 개선',
          },
          {
            type: 'macro',
            date: '2026-04-30',
            days_until: '0',
            label: '필수소비재 지지',
            affected_sectors: ['Consumer Defensive'],
            market_bias: '방어 섹터 support',
          },
        ],
      },
    })

    const discretionary = result.insights.find((sector) => sector.sector === 'Consumer Discretionary')
    const financials = result.insights.find((sector) => sector.sector === 'Financials')
    const staples = result.insights.find((sector) => sector.sector === 'Consumer Staples')

    expect(discretionary?.macroEvidence.map((event) => event.affected_sectors?.[0])).toEqual(['Consumer Cyclical'])
    expect(financials?.macroEvidence.map((event) => event.affected_sectors?.[0])).toEqual(['Financial'])
    expect(staples?.macroEvidence.map((event) => event.affected_sectors?.[0])).toEqual(['Consumer Defensive'])
    expect(discretionary?.eventExposureScore).toBeGreaterThan(0)
    expect(financials?.eventExposureScore).toBeGreaterThan(0)
    expect(staples?.eventExposureScore).toBeGreaterThan(0)
  })

  it('builds an accordion summary with focus and watch counts', () => {
    const sectorMood = deriveSectorMoodInsights({
      tickers: [
        makeTicker('NVDA', 'Semiconductors', '+2.4%', 'buy', 88, {
          macro_regime: 1,
          regime_adjustment: 0.8,
        }),
        makeTicker('NEE', 'Utilities', '-0.6%', 'avoid', 35, {
          macro_regime: -0.8,
          regime_adjustment: -0.7,
        }),
      ],
      marketRegime: regime,
      macroContext,
    })

    expect(buildMarketMoodSummary(regime, sectorMood)).toBe('risk_on · 주목 1개 / 주의 1개 · 매크로와 섹터 흐름')
  })
})
