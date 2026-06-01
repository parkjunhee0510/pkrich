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
            avoid: {
              '5d': {
                sample_count: 0,
                completed_count: 0,
                avg_return: null,
                median_return: null,
                win_rate: null,
                loss_rate: null,
                directional_win_rate: null,
                missing_count: 0,
                return_distribution: { positive: 0, negative: 0, flat: 0 },
                triple_barrier_outcomes: {},
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
            unknown: {
              unknown: {
                '5d': {
                  sample_count: 24,
                  completed_count: 24,
                  avg_return: 9.12,
                  median_return: 8.4,
                  win_rate: null,
                  loss_rate: null,
                  directional_win_rate: null,
                  missing_count: 0,
                  return_distribution: { positive: 20, negative: 4, flat: 0 },
                  triple_barrier_outcomes: {},
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
          ai_recommendation_backtest: {
            status: 'ok',
            basis: 'final_action',
            horizons: ['1d', '5d', '20d'],
            summary: {
              sample_count: 30,
              completed_20d_count: 24,
              best_action: 'buy',
              worst_action: 'watch',
              notes: ['AI recommendation backtest is observational.'],
            },
            by_action: {
              buy: {
                '1d': {
                  sample_count: 12,
                  completed_count: 12,
                  avg_return: 1.25,
                  median_return: 0.9,
                  win_rate: 0.6667,
                  loss_rate: 0.3333,
                  best_return: 4.1,
                  worst_return: -1.4,
                  missing_count: 0,
                },
                '5d': {
                  sample_count: 12,
                  completed_count: 11,
                  avg_return: 4.35,
                  median_return: 3.8,
                  win_rate: 0.7273,
                  loss_rate: 0.2727,
                  best_return: 9.8,
                  worst_return: -2.1,
                  missing_count: 1,
                },
                '20d': {
                  sample_count: 12,
                  completed_count: 11,
                  avg_return: 8.14,
                  median_return: 7.4,
                  win_rate: 0.725,
                  loss_rate: 0.275,
                  best_return: 18.2,
                  worst_return: -4.6,
                  missing_count: 1,
                },
              },
              watch: {
                '1d': {
                  sample_count: 10,
                  completed_count: 10,
                  avg_return: 0.2,
                  median_return: 0.1,
                  win_rate: null,
                  loss_rate: null,
                  best_return: 1.6,
                  worst_return: -1.1,
                  missing_count: 0,
                },
                '5d': {
                  sample_count: 10,
                  completed_count: 9,
                  avg_return: 0.75,
                  median_return: 0.4,
                  win_rate: null,
                  loss_rate: null,
                  best_return: 3.2,
                  worst_return: -2.4,
                  missing_count: 1,
                },
                '20d': {
                  sample_count: 10,
                  completed_count: 7,
                  avg_return: -1.1,
                  median_return: -0.8,
                  win_rate: null,
                  loss_rate: null,
                  best_return: 2.5,
                  worst_return: -6.4,
                  missing_count: 3,
                },
              },
              avoid: {
                '1d': {
                  sample_count: 8,
                  completed_count: 8,
                  avg_return: -0.45,
                  median_return: -0.3,
                  win_rate: 0.625,
                  loss_rate: 0.375,
                  best_return: 1.2,
                  worst_return: -2.5,
                  missing_count: 0,
                },
                '5d': {
                  sample_count: 8,
                  completed_count: 7,
                  avg_return: -2.2,
                  median_return: -1.6,
                  win_rate: 0.7143,
                  loss_rate: 0.2857,
                  best_return: 2.1,
                  worst_return: -5.9,
                  missing_count: 1,
                },
                '20d': {
                  sample_count: 8,
                  completed_count: 6,
                  avg_return: -3.8,
                  median_return: -2.9,
                  win_rate: 0.75,
                  loss_rate: 0.25,
                  best_return: 1.8,
                  worst_return: -8.3,
                  missing_count: 2,
                },
              },
            },
            conviction_buckets: {
              '65_80': {
                sample_count: 14,
                action_counts: { buy: 7, watch: 4, avoid: 3 },
                by_action: {
                  buy: {
                    '5d': {
                      sample_count: 7,
                      completed_count: 6,
                      avg_return: 3.4,
                      median_return: 2.7,
                      win_rate: 0.6667,
                      loss_rate: 0.3333,
                      best_return: 7.2,
                      worst_return: -2.1,
                      missing_count: 1,
                    },
                    '20d': {
                      sample_count: 7,
                      completed_count: 6,
                      avg_return: 6.4,
                      median_return: 5.9,
                      win_rate: 0.6667,
                      loss_rate: 0.3333,
                      best_return: 14.4,
                      worst_return: -4.6,
                      missing_count: 1,
                    },
                  },
                  watch: {
                    '5d': {
                      sample_count: 4,
                      completed_count: 4,
                      avg_return: 0.6,
                      median_return: 0.4,
                      win_rate: null,
                      loss_rate: null,
                      best_return: 1.8,
                      worst_return: -1.2,
                      missing_count: 0,
                    },
                    '20d': {
                      sample_count: 4,
                      completed_count: 3,
                      avg_return: -0.9,
                      median_return: -0.6,
                      win_rate: null,
                      loss_rate: null,
                      best_return: 2.5,
                      worst_return: -4.8,
                      missing_count: 1,
                    },
                  },
                  avoid: {
                    '5d': {
                      sample_count: 3,
                      completed_count: 3,
                      avg_return: -1.8,
                      median_return: -1.4,
                      win_rate: 0.6667,
                      loss_rate: 0.3333,
                      best_return: 1.3,
                      worst_return: -4.2,
                      missing_count: 0,
                    },
                    '20d': {
                      sample_count: 3,
                      completed_count: 2,
                      avg_return: -2.4,
                      median_return: -2.4,
                      win_rate: 0.5,
                      loss_rate: 0.5,
                      best_return: 1.8,
                      worst_return: -6.6,
                      missing_count: 1,
                    },
                  },
                },
              },
              '80_100': {
                sample_count: 8,
                action_counts: { buy: 5, watch: 2, avoid: 1 },
                by_action: {
                  buy: {
                    '5d': {
                      sample_count: 5,
                      completed_count: 5,
                      avg_return: 5.25,
                      median_return: 4.9,
                      win_rate: 0.8,
                      loss_rate: 0.2,
                      best_return: 9.8,
                      worst_return: -1.2,
                      missing_count: 0,
                    },
                    '20d': {
                      sample_count: 5,
                      completed_count: 0,
                      avg_return: null,
                      median_return: null,
                      win_rate: null,
                      loss_rate: null,
                      best_return: null,
                      worst_return: null,
                      missing_count: 5,
                    },
                  },
                  watch: {
                    '5d': {
                      sample_count: 2,
                      completed_count: 2,
                      avg_return: 0.9,
                      median_return: 0.9,
                      win_rate: null,
                      loss_rate: null,
                      best_return: 1.4,
                      worst_return: 0.4,
                      missing_count: 0,
                    },
                    '20d': {
                      sample_count: 2,
                      completed_count: 1,
                      avg_return: -1.6,
                      median_return: -1.6,
                      win_rate: null,
                      loss_rate: null,
                      best_return: -1.6,
                      worst_return: -1.6,
                      missing_count: 1,
                    },
                  },
                  avoid: {
                    '5d': {
                      sample_count: 1,
                      completed_count: 1,
                      avg_return: -2.3,
                      median_return: -2.3,
                      win_rate: 1,
                      loss_rate: 0,
                      best_return: -2.3,
                      worst_return: -2.3,
                      missing_count: 0,
                    },
                    '20d': {
                      sample_count: 1,
                      completed_count: 1,
                      avg_return: -5.5,
                      median_return: -5.5,
                      win_rate: 1,
                      loss_rate: 0,
                      best_return: -5.5,
                      worst_return: -5.5,
                      missing_count: 0,
                    },
                  },
                },
              },
            },
            ticker_leaderboard: [
              {
                ticker: 'NVDA',
                signals: 6,
                buy_signals: 5,
                avoid_signals: 0,
                completed_5d_count: 6,
                completed_20d_count: 5,
                avg_return_5d: 4.6,
                avg_return_20d: 8.9,
                win_rate_5d: 0.8333,
                win_rate_20d: 0.8,
              },
            ],
            notable_examples: {
              best: [
                {
                  signal_date: '2026-04-10',
                  ticker: 'NVDA',
                  action: 'buy',
                  conviction: 88,
                  return_5d: 6.7,
                  return_20d: 18.2,
                  catalyst_tag: 'earnings',
                  regime: 'risk_on',
                },
              ],
              worst: [
                {
                  signal_date: '2026-04-12',
                  ticker: 'TSLA',
                  action: 'buy',
                  conviction: 82,
                  return_5d: -2.1,
                  return_20d: -6.4,
                  catalyst_tag: 'delivery',
                  regime: 'risk_off',
                },
              ],
            },
          },
        },
        loading: false,
        error: null,
      }
    }

    if (relativePath === 'output/data/strategy_simulator.json') {
      return {
        data: {
          schema_version: 1,
          status: 'ok',
          as_of: '2026-05-06',
          mode: 'observational_long_only',
          basis: 'final_action',
          inputs: { signal_count: 1, usable_signal_count: 1, price_row_count: 2 },
          assumptions: { initial_capital: 100000, fee_rate: 0.001, slippage_rate: 0.0005 },
          presets: {
            conservative: strategyPreset('보수형', 2.1),
            balanced: strategyPreset('균형형', 4.2),
            aggressive: strategyPreset('공격형', 5.4),
          },
          notes: ['Strategy simulator is observational.'],
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
    expectTextContent('BUY 5D')
    expect(screen.getByText('+4.77%')).toBeInTheDocument()
    expect(screen.getByText('히트율 71.1% · 평가완료 45건 기준 · 전체 BUY 62건')).toBeInTheDocument()
    expectTextContent('WATCH 5D')
    expect(screen.getByText('방향 없음 · 평가완료 87건 기준 · 전체 WATCH 139건')).toBeInTheDocument()
    expectTextContent('AVOID 5D')
    expect(screen.getByText('전체 AVOID 표본 없음')).toBeInTheDocument()
    expect(screen.getByText('5D 평균 +4.77% · 전체 표본 62건')).toBeInTheDocument()
    expect(screen.getByText('미분류')).toBeInTheDocument()
    expect(screen.getByText('5D 평균 +9.12% · 평가완료 24건 기준 · 전체 표본 24건')).toBeInTheDocument()
    expect(screen.getByText('상위 팩터')).toBeInTheDocument()
    expect(screen.getByText('momentum')).toBeInTheDocument()
    expect(screen.getByText('최근 액션 변경')).toBeInTheDocument()
    expect(screen.getAllByText('AMD').length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: 'AI 추천 백테스팅' })).toBeInTheDocument()
    expect(screen.getByText('BUY 추천 승률')).toBeInTheDocument()
    expect(screen.getAllByText('72.5%').length).toBeGreaterThan(0)
    expect(screen.getByText('고확신 BUY')).toBeInTheDocument()
    expect(screen.getByText('+6.40%')).toBeInTheDocument()
    expect(screen.getByText('AVOID 방어 성공률')).toBeInTheDocument()
    expect(screen.getAllByText('75.0%').length).toBeGreaterThan(0)
    expect(screen.getByText('잘 맞은 추천')).toBeInTheDocument()
    expect(screen.getByText('틀린 추천')).toBeInTheDocument()
    expect(screen.getByText('NVDA')).toBeInTheDocument()
    expect(screen.getByText('TSLA')).toBeInTheDocument()
    expect(screen.getByText('2026-04-10')).toBeInTheDocument()
    expect(screen.getByText('2026-04-12')).toBeInTheDocument()
    expect(screen.getByText('+18.20%')).toBeInTheDocument()
    expect(screen.getByText('-6.40%')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '전략 시뮬레이터' })).toBeInTheDocument()
    expect(screen.getAllByText('균형형').length).toBeGreaterThan(0)
    expect(screen.getByText('LLM 방향 진단')).toBeInTheDocument()
  })
})

function expectTextContent(text: string) {
  expect(
    screen.getByText((_, element) => element?.textContent === text),
  ).toBeInTheDocument()
}

function strategyPreset(label: string, totalReturn: number) {
  return {
    label,
    description: 'sample',
    params: {
      initial_capital: 100000,
      position_size_pct: 0.1,
      max_positions: 8,
      stop_loss_pct: -0.08,
      take_profit_pct: 0.18,
      fee_rate: 0.001,
      slippage_rate: 0.0005,
    },
    summary: {
      initial_capital: 100000,
      ending_equity: 104200,
      total_return_pct: totalReturn,
      realized_pnl: 1200,
      unrealized_pnl: 3000,
      cash: 75000,
      cash_pct: 0.72,
      invested_value: 29200,
      invested_pct: 0.28,
      max_drawdown_pct: -3.1,
      trade_count: 2,
      closed_trade_count: 1,
      open_position_count: 1,
      winning_trade_count: 1,
      losing_trade_count: 0,
      win_rate: 1,
      avg_closed_trade_return_pct: 12.3,
      skipped_buy_count: 0,
    },
    equity_curve: [
      {
        date: '2026-05-06',
        equity: 104200,
        cash: 75000,
        invested_value: 29200,
        realized_pnl: 1200,
        unrealized_pnl: 3000,
        drawdown_pct: 0,
        open_position_count: 1,
      },
    ],
    trades: [
      {
        ticker: 'AAPL',
        entry_date: '2026-04-02',
        exit_date: '2026-04-03',
        exit_reason: 'take_profit',
        return_pct: 12.3,
        realized_pnl: 1200,
        llm_alignment: 'aligned',
      },
    ],
    open_positions: [
      {
        ticker: 'AMD',
        entry_date: '2026-04-02',
        latest_date: '2026-04-03',
        return_pct: 8.1,
        unrealized_pnl: 3000,
        llm_alignment: 'conflict',
      },
    ],
    entry_candidates: [
      {
        rank: 1,
        ticker: 'RKLB',
        status: 'pending_next_open',
        status_label: '다음 open 대기',
        signal_date: '2026-05-06',
        conviction: 91,
        entry_date: null,
        entry_price: null,
        stop_price: null,
        take_profit_price: null,
        position_size_pct: 0.1,
        target_notional: 10420,
        required_cash: null,
        available_cash: 75000,
        llm_alignment: 'aligned',
        signal_direction: 'bull',
        llm_direction: 'bull',
        reason: '다음 거래일 open 가격 필요',
      },
    ],
    skipped_entries: { total_count: 0, by_reason: {}, examples: [] },
    llm_direction_diagnostics: {
      aligned: {
        trade_count: 1,
        closed_trade_count: 1,
        open_position_count: 0,
        realized_pnl: 1200,
        unrealized_pnl: 0,
        avg_trade_return_pct: 12.3,
        win_rate: 1,
      },
      conflict: {
        trade_count: 1,
        closed_trade_count: 0,
        open_position_count: 1,
        realized_pnl: 0,
        unrealized_pnl: 3000,
        avg_trade_return_pct: 8.1,
        win_rate: null,
      },
      missing: {
        trade_count: 0,
        closed_trade_count: 0,
        open_position_count: 0,
        realized_pnl: 0,
        unrealized_pnl: 0,
        avg_trade_return_pct: null,
        win_rate: null,
      },
    },
  }
}
