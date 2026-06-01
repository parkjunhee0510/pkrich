import { describe, expect, it } from 'vitest';

import type {
  PMEventExposureItem,
  PMSwapCandidate,
  PortfolioRisk,
  PortfolioSummaryData,
  TickerAnalysisData,
} from '../types';
import {
  buildPortfolioCommandCenter,
  PORTFOLIO_RISK_TERM_HELP,
} from './portfolioCommandCenter';

const summary: PortfolioSummaryData = {
  total_market_value: 100_000,
  total_cost_basis: 90_000,
  total_unrealized_pnl: 10_000,
  total_unrealized_return_pct: 11.11,
  positions: [
    {
      ticker: 'AAPL',
      shares: 100,
      avg_cost: 100,
      currency: 'USD',
      market_price: 180,
      market_value: 45_000,
      cost_basis: 10_000,
      unrealized_pnl: 35_000,
      unrealized_return_pct: 350,
    },
    {
      ticker: 'AMD',
      shares: 100,
      avg_cost: 100,
      currency: 'USD',
      market_price: 130,
      market_value: 30_000,
      cost_basis: 10_000,
      unrealized_pnl: 20_000,
      unrealized_return_pct: 200,
    },
    {
      ticker: 'CAT',
      shares: 100,
      avg_cost: 100,
      currency: 'USD',
      market_price: 250,
      market_value: 25_000,
      cost_basis: 10_000,
      unrealized_pnl: 15_000,
      unrealized_return_pct: 150,
    },
  ],
};

const risk: PortfolioRisk = {
  hhi: 3400,
  portfolio_beta: 1.24,
  var_95: 2.8,
  risk_grade: 'C',
  concentration_warning: 'Technology 비중이 높습니다.',
  positions_by_weight: [
    { ticker: 'AAPL', weight_pct: 45, sector: 'Technology', market_value: 45_000, atr_risk_usd: 1800 },
    { ticker: 'AMD', weight_pct: 30, sector: 'Technology', market_value: 30_000, atr_risk_usd: 1200 },
    { ticker: 'CAT', weight_pct: 25, sector: 'Industrials', market_value: 25_000, atr_risk_usd: 900 },
  ],
  sector_exposure: {
    Technology: 75,
    Industrials: 25,
  },
  correlation_pairs: [
    {
      ticker_1: 'AAPL',
      ticker_2: 'AMD',
      correlation: '0.81',
      warning: '두 기술주가 같은 방향으로 움직일 가능성이 큽니다.',
    },
  ],
};

const events: PMEventExposureItem[] = [
  {
    ticker: 'AMD',
    event_risk_score: 92,
    event_label: '실적 발표',
    event_date: '2026-05-15',
    days_until: 2,
    summary: '실적 발표 전 변동성이 커질 수 있습니다.',
    reasons: ['실적 변동성'],
    review_points: ['포지션 크기 확인'],
  },
  {
    ticker: 'CAT',
    event_risk_score: 68,
    event_label: '배당락',
    event_date: '2026-05-20',
    days_until: 7,
    summary: '배당락 전후 가격 흐름 확인이 필요합니다.',
    reasons: ['현금흐름 확인'],
    review_points: ['배당 영향 점검'],
  },
];

const swaps: PMSwapCandidate[] = [
  {
    held_ticker: 'AAPL',
    candidate_ticker: 'CAT',
    swap_candidate_score: 76,
    summary: '집중도 완화를 위해 대체 후보를 검토합니다.',
    reasons: ['집중도 완화'],
    overlap_context: '섹터 분산',
    review_points: ['AAPL 비중과 CAT 신규 비중 비교'],
  },
];

const tickers = [
  {
    ticker: 'AAPL',
    name: 'Apple',
    decision: {
      action: 'watch',
      conviction: 62,
      reason: '집중도 완화',
      valid_until: '2026-05-31',
      factors: {},
    },
  },
] as TickerAnalysisData[];

describe('buildPortfolioCommandCenter', () => {
  it('prioritizes actionable event, swap, concentration, and correlation items', () => {
    const result = buildPortfolioCommandCenter({
      portfolioSummary: summary,
      portfolioRisk: risk,
      pmEventExposure: events,
      pmSwapCandidates: swaps,
      tickerAnalyses: tickers,
    });

    expect(result.queue.map((item) => item.id)).toEqual([
      'event:AMD',
      'event:CAT',
      'swap:AAPL:CAT',
      'concentration:AMD',
      'concentration:CAT',
    ]);
    expect(result.queue[0]).toMatchObject({
      ticker: 'AMD',
      type: 'event',
      title: '실적 발표',
      severity: 'high',
      termHelp: PORTFOLIO_RISK_TERM_HELP.event,
    });
    expect(result.queue[0].meta).toContain('D-2');
  });

  it('builds Korean risk insights with explanatory help for HHI, beta, VaR, and correlation', () => {
    const result = buildPortfolioCommandCenter({
      portfolioSummary: summary,
      portfolioRisk: risk,
      pmEventExposure: events,
      pmSwapCandidates: swaps,
      tickerAnalyses: tickers,
    });

    expect(result.insights.map((item) => item.id)).toContain('hhi');
    expect(result.insights.map((item) => item.id)).toContain('beta');
    expect(result.insights.map((item) => item.id)).toContain('var');
    expect(result.insights.map((item) => item.id)).toContain('correlation');
    expect(result.insights.find((item) => item.id === 'hhi')?.termHelp).toBe(
      PORTFOLIO_RISK_TERM_HELP.hhi,
    );
    expect(result.insights.find((item) => item.id === 'beta')?.value).toBe('1.24');
    expect(result.insights.find((item) => item.id === 'var')?.value).toBe('2.8%');
    expect(result.insights.find((item) => item.id === 'correlation')?.detail).toContain(
      'AAPL/AMD',
    );
  });

  it('returns stable empty state when portfolio data is missing', () => {
    const result = buildPortfolioCommandCenter({
      portfolioSummary: {
        total_market_value: 0,
        total_cost_basis: 0,
        total_unrealized_pnl: 0,
        total_unrealized_return_pct: 0,
        positions: [],
      },
      portfolioRisk: null,
      pmEventExposure: [],
      pmSwapCandidates: [],
      tickerAnalyses: [],
    });

    expect(result.queue).toEqual([]);
    expect(result.insights).toEqual([]);
    expect(result.hasData).toBe(false);
  });
});
