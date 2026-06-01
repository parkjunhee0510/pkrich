import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { Backtest } from './Backtest'

vi.mock('../hooks/useDashboardData', () => ({
  useDashboardData: () => ({
    data: {
      days: [
        {
          date: '2026-05-06',
          market_overview: [],
          macro_context: null,
          market_regime: null,
          tickers: [],
        },
      ],
    },
    loading: false,
    error: null,
  }),
}))

vi.mock('../hooks/useJsonResource', () => ({
  useJsonResource: (relativePath: string) => {
    if (relativePath === 'output/data/backtest_summary.json') {
      return {
        data: {
          status: 'ok',
          strategy: 'signal_following',
          signals: 12,
          win_rate: '58.3%',
          avg_return: '+2.10%',
          cumulative_return: '+9.20%',
          best_return: '+12.00%',
          worst_return: '-4.00%',
        },
        loading: false,
        error: null,
      }
    }

    if (relativePath === 'output/data/monthly_summary.json') {
      return {
        data: {
          month: '2026-05',
          status: 'ok',
          trading_days: 5,
          start_date: '2026-05-01',
          end_date: '2026-05-06',
          top_tickers: [],
          top_sectors: [],
        },
        loading: false,
        error: null,
      }
    }

    if (relativePath === 'output/data/routing_outcome.json') {
      return { data: null, loading: false, error: null }
    }

    if (relativePath === 'output/data/analysis_performance.json') {
      return {
        data: {
          schema_version: 1,
          as_of: '2026-05-06',
          summary: {
            sample_count: 225,
            decision_count: 23,
            completed_return_windows: ['1d', '5d'],
            mode: 'shadow_observational',
            notes: [
              'Performance analytics are observational and do not change official decisions.',
            ],
          },
          signal_performance: {
            buy: {
              '5d': {
                sample_count: 62,
                completed_count: 45,
                avg_return: 4.7678,
                median_return: 3.61,
                win_rate: 0.7111,
                loss_rate: 0.2889,
                directional_win_rate: 0.7111,
                missing_count: 17,
                return_distribution: { positive: 32, negative: 12, flat: 1 },
                triple_barrier_outcomes: { hit: 24, stop: 21 },
              },
            },
            watch: {
              '5d': {
                sample_count: 139,
                completed_count: 87,
                avg_return: 2.6582,
                median_return: 1.72,
                win_rate: null,
                loss_rate: null,
                directional_win_rate: null,
                missing_count: 52,
                return_distribution: { positive: 60, negative: 27, flat: 0 },
                triple_barrier_outcomes: { hit: 47, pending: 4, stop: 36 },
              },
            },
          },
          conviction_calibration: {
            status: 'observational',
            bucket_edges: ['65_80'],
            buckets: {
              '65_80': {
                sample_count: 62,
                action_counts: { buy: 62 },
                avg_return_1d: 1.6362,
                avg_return_5d: 4.7678,
                avg_return_20d: null,
                buy_win_rate: 0.7111,
                avoid_win_rate: null,
              },
            },
          },
          factor_attribution: {
            status: 'observed_association',
            missing_factor_sample_count: 24,
            factors: {
              momentum: {
                sample_count: 80,
                avg_score: 12.1,
                positive_score_count: 80,
                negative_score_count: 0,
                avg_forward_return_5d: 4.2,
                avg_forward_return_20d: null,
                best_action_context: {
                  action: 'buy',
                  sample_count: 45,
                  avg_return_5d: 4.7678,
                },
                worst_action_context: {
                  action: 'watch',
                  sample_count: 35,
                  avg_return_5d: 2.6582,
                },
              },
            },
          },
          regime_performance: {
            risk_on: {
              buy: {
                '5d': {
                  sample_count: 62,
                  completed_count: 45,
                  avg_return: 4.7678,
                  median_return: 3.61,
                  win_rate: 0.7111,
                  loss_rate: 0.2889,
                  directional_win_rate: 0.7111,
                  missing_count: 17,
                  return_distribution: { positive: 32, negative: 12, flat: 1 },
                  triple_barrier_outcomes: { hit: 24, stop: 21 },
                },
              },
            },
          },
          action_change_reasons: [
            {
              ticker: 'AMD',
              previous_action: 'watch',
              current_action: 'buy',
              previous_conviction: 61,
              current_conviction: 71,
              previous_regime: 'risk_on',
              current_regime: 'risk_on',
              reason_codes: ['action_upgraded', 'conviction_crossed_buy_threshold'],
              summary: 'AMD changed watch -> buy; conviction crossed buy threshold.',
              contributors: [],
            },
          ],
        },
        loading: false,
        error: null,
      }
    }

    return { data: null, loading: false, error: null }
  },
}))

describe('Backtest analysis performance panel', () => {
  it('renders shadow signal performance from analysis_performance.json', () => {
    render(<Backtest />)

    expect(screen.getByRole('heading', { name: '분석 성과 추적' })).toBeInTheDocument()
    expect(screen.getByText('2026-05-06 · 표본 225건 · 결정 23건')).toBeInTheDocument()
    expect(screen.getByText('BUY 5D')).toBeInTheDocument()
    expect(screen.getByText('+4.77%')).toBeInTheDocument()
    expect(screen.getByText('히트율 71.1% · 완료 45/62')).toBeInTheDocument()
    expect(screen.getByText('WATCH 5D')).toBeInTheDocument()
    expect(screen.getByText('표본 139건 · 완료 87건')).toBeInTheDocument()
    expect(screen.getByText('상위 팩터')).toBeInTheDocument()
    expect(screen.getByText('momentum')).toBeInTheDocument()
    expect(screen.getByText('최근 액션 변경')).toBeInTheDocument()
    expect(screen.getByText('AMD')).toBeInTheDocument()
  })
})
