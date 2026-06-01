import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AiRecommendationBacktestPanel } from './AiRecommendationBacktestPanel'
import type {
  AiRecommendationBacktestPayload,
  AiRecommendationWindowStats,
} from '../types'

function makeStats(overrides: Partial<AiRecommendationWindowStats> = {}): AiRecommendationWindowStats {
  return {
    sample_count: 1,
    completed_count: 1,
    avg_return: 1.2,
    median_return: 1.1,
    win_rate: 0.75,
    loss_rate: 0.25,
    best_return: 2.4,
    worst_return: -0.5,
    missing_count: 0,
    ...overrides,
  }
}

function makeEmptyStats(): AiRecommendationWindowStats {
  return makeStats({
    sample_count: 0,
    completed_count: 0,
    avg_return: null,
    median_return: null,
    win_rate: null,
    loss_rate: null,
    best_return: null,
    worst_return: null,
    missing_count: 0,
  })
}

function makePayload(): AiRecommendationBacktestPayload {
  const buyStats = makeStats()
  const watchStats = makeStats({
    win_rate: null,
    loss_rate: null,
  })
  const avoidStats = makeEmptyStats()

  return {
    status: 'ok',
    basis: 'final_action',
    horizons: ['1d', '5d', '20d'],
    summary: {
      sample_count: 2,
      completed_20d_count: 1,
      best_action: 'buy',
      worst_action: 'watch',
      notes: [],
    },
    by_action: {
      buy: { '1d': buyStats, '5d': buyStats, '20d': buyStats },
      watch: { '1d': watchStats, '5d': watchStats, '20d': watchStats },
      avoid: { '1d': avoidStats, '5d': avoidStats, '20d': avoidStats },
    },
    conviction_buckets: {
      '65_80': {
        sample_count: 1,
        action_counts: { buy: 1 },
        by_action: {
          buy: {
            '20d': buyStats,
          },
        },
      },
    },
    ticker_leaderboard: [],
    notable_examples: {
      best: [
        {
          signal_date: '2026-05-01',
          ticker: 'AMD',
          action: 'buy',
          conviction: 70,
          return_5d: 3.2,
          return_20d: 8.4,
          catalyst_tag: 'earnings',
          regime: 'risk_on',
        },
      ],
      worst: [
        {
          signal_date: '2026-05-02',
          ticker: 'AAPL',
          action: 'watch',
          conviction: 58,
          return_5d: -1.4,
          return_20d: -3.6,
          catalyst_tag: 'macro',
          regime: 'neutral',
        },
      ],
    },
  }
}

describe('AiRecommendationBacktestPanel', () => {
  it('labels buy win rate as evaluated-sample based', () => {
    const payload = makePayload()
    payload.by_action.buy['20d'] = makeStats({
      sample_count: 128,
      completed_count: 45,
      avg_return: 17.7329,
      win_rate: 0.8889,
    })

    render(<AiRecommendationBacktestPanel payload={payload} />)

    expect(
      screen.getByText('20D 평균 +17.73% · 평가완료 45건 기준 · 전체 BUY 128건'),
    ).toBeInTheDocument()
  })

  it('labels high-conviction buy summary as evaluated-sample based', () => {
    const payload = makePayload()
    payload.conviction_buckets['65_80'].by_action.buy['20d'] = makeStats({
      sample_count: 128,
      completed_count: 45,
      avg_return: 17.7329,
      win_rate: 0.8889,
    })

    render(<AiRecommendationBacktestPanel payload={payload} />)

    expect(
      screen.getByText('승률 88.9% · 평가완료 45건 기준 · 전체 고확신 BUY 128건 · 65-80'),
    ).toBeInTheDocument()
  })

  it('distinguishes no samples from non-directional watch win rates', () => {
    render(<AiRecommendationBacktestPanel payload={makePayload()} />)

    const watchRow = screen.getAllByText('WATCH')[0].closest('tr')
    expect(watchRow).not.toBeNull()
    expect(within(watchRow as HTMLElement).getByText('방향 없음')).toBeInTheDocument()

    const avoidRow = screen.getByText('AVOID').closest('tr')
    expect(avoidRow).not.toBeNull()
    expect(within(avoidRow as HTMLElement).getAllByText('표본 없음')).toHaveLength(4)
    expect(within(avoidRow as HTMLElement).getByText('0/0')).toBeInTheDocument()
  })

  it('renders the compact insufficient-data state', () => {
    const payload = makePayload()
    payload.status = 'insufficient_data'
    payload.summary = {
      sample_count: 0,
      completed_20d_count: 0,
      best_action: null,
      worst_action: null,
      notes: ['No tracked signals are available yet.'],
    }
    payload.by_action = {}
    payload.conviction_buckets = {}
    payload.ticker_leaderboard = []
    payload.notable_examples = { best: [], worst: [] }

    render(<AiRecommendationBacktestPanel payload={payload} />)

    expect(screen.getByRole('heading', { name: 'AI 추천 백테스팅' })).toBeInTheDocument()
    expect(
      screen.getByText('평가 기간이 더 쌓이면 AI 추천 백테스팅이 표시됩니다.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('액션별 추천 성과')).not.toBeInTheDocument()
  })

  it('stays hidden when the ai recommendation backtest payload is absent', () => {
    const { container } = render(<AiRecommendationBacktestPanel payload={null} />)

    expect(container).toBeEmptyDOMElement()
  })
})
