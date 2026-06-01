import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { Backtest } from './Backtest'

vi.mock('../hooks/useDashboardData', () => ({
  useDashboardData: () => ({
    data: {
      days: [
        {
          date: '2026-05-07',
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
          signals: 0,
          win_rate: 'N/A',
          avg_return: 'N/A',
          cumulative_return: 'N/A',
          best_return: 'N/A',
          worst_return: 'N/A',
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
          end_date: '2026-05-07',
          top_tickers: [],
          top_sectors: [],
        },
        loading: false,
        error: null,
      }
    }

    if (relativePath === 'output/data/routing_outcome.json') {
      return {
        data: {
          schema_version: 1,
          run_count: 1,
          evaluated_signals: 0,
          latest_run_date: '2026-05-07',
          status: 'no_data',
          summary: {
            deep_selected_count: 0,
            economy_only_count: 0,
            portfolio_priority_count: 0,
            deep_selected_avg_return_20d: null,
            economy_only_avg_return_20d: null,
            portfolio_priority_avg_return_20d: null,
            deep_selected_hit_rate: null,
            economy_only_hit_rate: null,
            portfolio_priority_hit_rate: null,
            avg_return_delta_20d: null,
            hit_rate_delta: null,
          },
          periods: [],
          latest_run: {
            run_date: '2026-05-07',
            trigger_range: [25, 75],
            max_daily_ensemble: 5,
            portfolio_priority: true,
            deep_pass_count: 2,
            selected_tickers: ['AMD', 'AAPL'],
            skipped_due_to_priority: ['KO'],
            router_budget_estimate: {
              selected_count: 2,
              estimated_incremental_cost_usd: 0.0246,
              estimated_monthly_cost_usd: 0.5412,
            },
            tickers: [
              {
                ticker: 'AMD',
                selected_for_deep: true,
                reason: 'in_trigger_range',
                in_portfolio: false,
                conviction: 67,
                action: 'buy',
                router_priority_score: 42.75,
                router_reason_codes: ['uncertainty_boundary', 'evidence_gap'],
                skipped_due_to_priority: false,
              },
              {
                ticker: 'KO',
                selected_for_deep: false,
                reason: 'in_trigger_range',
                in_portfolio: false,
                conviction: 52,
                action: 'watch',
                router_priority_score: 12,
                router_reason_codes: ['volatility'],
                skipped_due_to_priority: true,
              },
            ],
          },
        },
        loading: false,
        error: null,
      }
    }

    if (relativePath === 'output/data/analysis_performance.json') {
      return { data: null, loading: false, error: null }
    }

    return { data: null, loading: false, error: null }
  },
}))

describe('Backtest router metadata panel', () => {
  it('renders router priority scores and reason codes from routing_outcome.json', () => {
    render(<Backtest />)

    const heading = screen.getByRole('heading', { name: 'Smart Router 우선순위' })
    const section = heading.closest('section') as HTMLElement

    expect(within(section).getByText('예상 월간 deep 비용')).toBeInTheDocument()
    expect(within(section).getByText('$0.5412')).toBeInTheDocument()
    expect(within(section).getByText('AMD')).toBeInTheDocument()
    expect(within(section).getByText('42.75')).toBeInTheDocument()
    expect(within(section).getByText('uncertainty_boundary, evidence_gap')).toBeInTheDocument()
    expect(within(section).getByText('KO')).toBeInTheDocument()
    expect(within(section).getByText('priority skip')).toBeInTheDocument()
  })
})
