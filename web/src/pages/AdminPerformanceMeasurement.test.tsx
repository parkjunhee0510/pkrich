import { render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Admin } from './Admin'

const useJsonResourceMock = vi.hoisted(() => vi.fn())

vi.mock('../hooks/useJsonResource', () => ({
  useJsonResource: useJsonResourceMock,
}))

const costLogPayload = {
  schema_version: 1,
  runs: [
    {
      run_date: '2026-05-07',
      success: true,
      total_cost_usd: 0.4316217,
      profiles: {
        economy: {
          cost_usd: 0.1910125,
          tokens: 525329,
          calls: 145,
          models: { 'gpt-5.4-mini': 145 },
        },
        standard: {
          cost_usd: 0.1163125,
          tokens: 72883,
          calls: 15,
          models: { 'gpt-5.4-mini': 15 },
        },
        deep: {
          cost_usd: 0.1242967,
          tokens: 90892,
          calls: 19,
          models: { 'gpt-5.4-mini': 19 },
        },
      },
      routing: {
        ensemble_enabled: true,
        eligible_count: 23,
        selected_count: 5,
        skipped_due_to_cap_count: 18,
        conflicted_count: 3,
      },
      deep_pass_value: {
        deep_cost_usd: 0.1242967,
        selected_ticker_count: 5,
        cost_per_selected_ticker_usd: 0.024859,
        share_of_total_cost: 0.288,
        worth_it_hint: 'conflict_review_value',
      },
    },
  ],
}

const performanceBaseline = {
  schema_version: 1,
  as_of: '2026-05-07',
  status: 'ok',
  latest_run_date: '2026-05-07',
  monthly_budget_usd: 10,
  json_health: {
    status: 'ok',
    invalid_json_count: 0,
    issues: [],
  },
  cost: {
    total_cost_usd: 0.4316217,
    estimated_monthly_cost_usd: 9.4957,
    monthly_budget_usd: 10,
    budget_usage_ratio: 0.9496,
    llm_calls: 179,
    ticker_count_for_rate: 23,
    llm_calls_per_ticker: 7.783,
    deep_selected_count: 5,
    routing_conflicted_count: 3,
    budget_guard_would_block_count: 6,
    budget_guard_blocked_count: 0,
  },
  quality: {
    validated_ticker_count: 283,
    validation_failure_count: 17,
    validation_failure_rate: 0.0601,
    hallucination_warning_count: 35,
    hallucination_ratio: 0.1237,
    fact_warning_count: 8,
    consistency_warning_count: 0,
  },
  evidence: {
    provider: 'cache',
    ticker_count: 23,
    covered_ticker_count: 0,
    coverage_ratio: 0,
    average_coverage_score: 0,
    average_freshness_score: 0,
    candidate_ticker_count: 5,
    searched_ticker_count: 0,
    cache_ttl_hours: 48,
    cache_hit_count: 4,
    stale_cache_hit_count: 1,
    cache_hit_ratio: 0.8,
    stale_cache_hit_ratio: 0.25,
    average_cache_age_hours: 6,
    max_cache_age_hours: 24,
    provider_candidate_count: 5,
    status_counts: { no_evidence: 23 },
    priority_ticker_count: 5,
    priority_covered_ticker_count: 2,
    priority_coverage_ratio: 0.4,
    priority_status_counts: { covered: 2, no_evidence: 3 },
  },
  signals: {
    turnover_status: 'ok',
    avg_turnover: 0.047,
    kelly_status: 'ok',
  },
}

const performanceTrends = {
  schema_version: 1,
  as_of: '2026-05-07',
  monthly_budget_usd: 10,
  runs: [
    {
      run_date: '2026-05-06',
      success: true,
      total_cost_usd: 0.32,
      llm_calls: 120,
      hallucination_ratio: 0.08,
      validation_failure_count: 8,
      deep_selected_count: 3,
      budget_guard_would_block_count: 2,
    },
    {
      run_date: '2026-05-07',
      success: true,
      total_cost_usd: 0.4316217,
      llm_calls: 179,
      hallucination_ratio: 0.1237,
      validation_failure_count: 17,
      deep_selected_count: 5,
      budget_guard_would_block_count: 6,
    },
  ],
}

describe('Admin performance measurement panel', () => {
  beforeEach(() => {
    useJsonResourceMock.mockImplementation((relativePath: string) => {
      if (relativePath === 'output/data/performance_baseline.json') {
        return { data: performanceBaseline, loading: false, error: null }
      }
      if (relativePath === 'output/data/performance_trends.json') {
        return { data: performanceTrends, loading: false, error: null }
      }
      if (relativePath === 'output/data/cost_log.json') {
        return { data: costLogPayload, loading: false, error: null }
      }
      return { data: null, loading: false, error: null }
    })
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('cost_log.json')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(costLogPayload),
          })
        }
        return Promise.resolve({
          ok: false,
          json: () => Promise.resolve({}),
        })
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('renders read-only baseline and trend metrics from performance artifacts', async () => {
    render(<Admin />)

    const heading = await screen.findByRole('heading', { name: '성능 기준선' })
    const section = heading.closest('section') as HTMLElement

    expect(within(section).getByText('2026-05-07 · latest 2026-05-07')).toBeInTheDocument()
    expect(within(section).getByText('$9.50 / $10.00')).toBeInTheDocument()
    expect(within(section).getByText('95.0% 사용')).toBeInTheDocument()
    expect(within(section).getByText('179 calls')).toBeInTheDocument()
    expect(within(section).getByText('7.783 calls/ticker · deep 5건')).toBeInTheDocument()
    expect(within(section).getAllByText('12.4%')[0]).toBeInTheDocument()
    expect(within(section).getByText('validation 6.0% · fact 8건')).toBeInTheDocument()
    expect(within(section).getByText('0.0%')).toBeInTheDocument()
    expect(within(section).getByText('covered 0/23 · provider cache')).toBeInTheDocument()
    expect(within(section).getByText('Priority evidence')).toBeInTheDocument()
    expect(within(section).getByText('40.0%')).toBeInTheDocument()
    expect(within(section).getByText('2/5 prioritized; covered=2, no_evidence=3')).toBeInTheDocument()
    expect(within(section).getByText('Evidence cache')).toBeInTheDocument()
    expect(within(section).getByText('80.0%')).toBeInTheDocument()
    expect(within(section).getByText('1/4 stale; avg 6.0h, max 24h; TTL 48h')).toBeInTheDocument()
    expect(within(section).getByRole('cell', { name: '2026-05-07' })).toBeInTheDocument()
    expect(within(section).getByRole('cell', { name: '$0.432' })).toBeInTheDocument()
    expect(within(section).getByRole('cell', { name: '6' })).toBeInTheDocument()
  })
})
