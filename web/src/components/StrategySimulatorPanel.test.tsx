import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StrategySimulatorPanel } from './StrategySimulatorPanel'
import type { StrategySimulatorPayload, StrategySimulatorPreset } from '../types'

function makePayload(): StrategySimulatorPayload {
  return {
    schema_version: 1,
    status: 'ok',
    as_of: '2026-04-03',
    mode: 'observational_long_only',
    basis: 'final_action',
    inputs: { signal_count: 1, usable_signal_count: 1, price_row_count: 2 },
    assumptions: { initial_capital: 100000, fee_rate: 0.001, slippage_rate: 0.0005 },
    presets: {
      conservative: makePreset('보수형', 2.1),
      balanced: makePreset('균형형', 4.2),
      aggressive: makePreset('공격형', 5.4),
    },
    notes: ['Strategy simulator is observational.'],
    news_shadow: {
      status: 'ok',
      strategies: [
        {
          id: 'strong_news_llm_bull',
          label: '강한 뉴스 + LLM 강세',
          criteria: [
            'news_evidence.strength == strong',
            'llm_direction == bull',
            'positive news tone or recent hard catalyst',
          ],
          summary: {
            sample_count: 1,
            completed_1d_count: 1,
            avg_return_1d: 2.0,
            win_rate_1d: 1.0,
            completed_5d_count: 1,
            avg_return_5d: 5.0,
            win_rate_5d: 1.0,
            completed_20d_count: 0,
            avg_return_20d: null,
            win_rate_20d: null,
          },
          events: [
            {
              signal_date: '2026-04-01',
              ticker: 'AAPL',
              entry_date: '2026-04-02',
              entry_price: 101.0,
              news_score: 82.0,
              news_strength: 'strong',
              news_tone: 'bullish',
              llm_direction: 'bull',
              return_1d: 2.0,
              return_5d: 5.0,
              return_20d: null,
            },
          ],
        },
      ],
    },
    today_action_queue: {
      status: 'ok',
      as_of: '2026-04-03',
      basis: 'final_action',
      preset_key: 'balanced',
      preset_label: '균형형',
      summary: {
        enter_count: 1,
        watch_count: 1,
        skip_count: 1,
        hold_count: 1,
        top_action: 'enter',
      },
      items: [
        {
          queue: 'enter',
          decision_label: '진입 검토',
          rank: 1,
          ticker: 'RKLB',
          action_score: 88.5,
          status: 'entry_ready',
          status_label: '진입 가능',
          primary_reason: '다음 거래일 open 기준 진입 조건을 확인할 수 있는 후보입니다.',
          reason_chips: ['진입 조건 충족', '뉴스 강함', 'LLM 일치'],
          blocking_reasons: [],
          positive_reasons: ['entry_ready', 'strong_news', 'llm_aligned'],
          candidate_ref: { preset: 'balanced', candidate_rank: 1 },
          candidate: makePreset('균형형', 4.2).entry_candidates[0],
        },
        {
          queue: 'watch',
          decision_label: '보류',
          rank: 2,
          ticker: 'NVDA',
          action_score: 62,
          status: 'pending_next_open',
          status_label: '다음 open 대기',
          primary_reason: '다음 거래일 open 가격이 생성되면 진입 조건을 다시 확인합니다.',
          reason_chips: ['다음 open 대기', '뉴스 보통'],
          blocking_reasons: ['pending_next_open'],
          positive_reasons: ['moderate_news'],
          candidate_ref: { preset: 'balanced', candidate_rank: 2 },
          candidate: makePreset('균형형', 4.2).entry_candidates[1],
        },
        {
          queue: 'skip',
          decision_label: '제외',
          rank: 3,
          ticker: 'CASH',
          action_score: 28,
          status: 'insufficient_cash',
          status_label: '현금 부족',
          primary_reason: '목표 비중 진입에 필요한 현금이 부족해 제외합니다.',
          reason_chips: ['현금 부족'],
          blocking_reasons: ['insufficient_cash'],
          positive_reasons: [],
          candidate_ref: { preset: 'balanced', candidate_rank: 3 },
          candidate: {
            ...makePreset('균형형', 4.2).entry_candidates[0],
            rank: 3,
            ticker: 'CASH',
            status: 'insufficient_cash',
            status_label: '현금 부족',
          },
        },
      ],
      position_alerts: [
        {
          queue: 'hold',
          decision_label: '보유 관리',
          ticker: 'AMD',
          priority: 1,
          alert_score: 64,
          primary_reason: '보유 중인 포지션의 미실현 손익과 보유 기간을 확인합니다.',
          reason_chips: ['보유 중', '수익률 +8.10%', '보유 1일'],
          position_ref: { preset: 'balanced', ticker: 'AMD' },
          position: makePreset('균형형', 4.2).open_positions[0],
        },
      ],
      notes: ['오늘 행동 큐는 관찰용 화면입니다.'],
    },
  }
}

function makePreset(label: string, totalReturn: number): StrategySimulatorPreset {
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
        date: '2026-04-02',
        equity: 100000,
        cash: 90000,
        invested_value: 10000,
        realized_pnl: 0,
        unrealized_pnl: 0,
        drawdown_pct: 0,
        open_position_count: 1,
      },
      {
        date: '2026-04-03',
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
        signal_date: '2026-04-03',
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
        news_evidence: {
          score: 88,
          strength: 'strong',
          tone: 'bullish',
          llm_direction: 'bull',
          llm_alignment: 'aligned',
          catalyst_tag: 'launch_contract',
          catalyst_recency_score: 0.92,
          source_count: 6,
          has_recent_catalyst: true,
          has_hard_catalyst: true,
          reason_chips: ['positive_news', 'llm_bull_aligned', 'recent_catalyst', 'hard_catalyst', 'source_coverage'],
          summary: '최근 계약 뉴스와 LLM 강세 방향이 진입 후보 근거를 보강합니다.',
        },
        reason: '다음 거래일 open 가격 필요',
      },
      {
        rank: 2,
        ticker: 'NVDA',
        status: 'already_held',
        status_label: '이미 보유',
        signal_date: '2026-04-02',
        conviction: 84,
        entry_date: '2026-04-03',
        entry_price: 120,
        stop_price: 110.4,
        take_profit_price: 141.6,
        position_size_pct: 0.1,
        target_notional: 10000,
        required_cash: null,
        available_cash: 75000,
        llm_alignment: 'conflict',
        signal_direction: 'bull',
        llm_direction: 'bear',
        news_evidence: {
          score: 12,
          strength: 'insufficient',
          tone: 'neutral',
          llm_direction: 'bear',
          llm_alignment: 'conflict',
          catalyst_tag: null,
          catalyst_recency_score: null,
          source_count: 1,
          has_recent_catalyst: false,
          has_hard_catalyst: false,
          reason_chips: ['source_limited', 'llm_conflict', 'neutral_news'],
          summary: '최근 촉매와 출처 수가 부족해 뉴스 근거가 약합니다.',
        },
        reason: '현재 보유 중',
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

describe('StrategySimulatorPanel', () => {
  it('renders preset comparison and selected preset details', () => {
    render(<StrategySimulatorPanel payload={makePayload()} />)

    expect(screen.getByRole('heading', { name: '전략 시뮬레이터' })).toBeInTheDocument()
    expect(screen.getAllByText('보수형').length).toBeGreaterThan(0)
    expect(screen.getAllByText('균형형').length).toBeGreaterThan(0)
    expect(screen.getAllByText('공격형').length).toBeGreaterThan(0)
    expect(screen.getAllByText('+4.20%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('AMD').length).toBeGreaterThan(0)
    expect(screen.getAllByText('conflict').length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: '가상 계좌 가치 변화' })).toBeInTheDocument()
    expect(screen.getByText('현금 + 열린 포지션 평가액 · 매수/매도 비용 반영')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '자산 곡선' })).not.toBeInTheDocument()
    expect(screen.getByText('LLM 방향 진단')).toBeInTheDocument()
  })

  it('renders entry candidates as top cards and a detail table', () => {
    render(<StrategySimulatorPanel payload={makePayload()} />)

    expect(screen.getByRole('heading', { name: '진입 후보 Top 3' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '진입 후보 상세' })).toBeInTheDocument()
    expect(screen.getAllByText('RKLB').length).toBeGreaterThan(0)
    expect(screen.getAllByText('뉴스 근거 강함').length).toBeGreaterThan(0)
    expect(screen.getAllByText('88점').length).toBeGreaterThan(0)
    expect(screen.getByText('최근 계약 뉴스와 LLM 강세 방향이 진입 후보 근거를 보강합니다.')).toBeInTheDocument()
    expect(screen.getByText('긍정 뉴스')).toBeInTheDocument()
    expect(screen.getByText('LLM 강세 일치')).toBeInTheDocument()
    expect(screen.getByText('최근 촉매')).toBeInTheDocument()
    expect(screen.getByText('강한 촉매')).toBeInTheDocument()
    const entrySection = screen.getByRole('region', { name: '오늘 진입 후보' })
    const rklbCard = within(entrySection).getAllByText('RKLB')[0].closest('.strategy-entry-candidate-card')
    expect(rklbCard).not.toBeNull()
    expect(within(rklbCard as HTMLElement).queryByText('출처 충분')).not.toBeInTheDocument()
    expect(screen.getAllByText('다음 open 대기').length).toBeGreaterThan(0)
    expect(screen.getAllByText('진입 기준 다음 거래일 open').length).toBeGreaterThan(0)
    expect(screen.getByText('확정 진입가 open 데이터 대기')).toBeInTheDocument()
    expect(screen.getByText('손절/익절 진입가 확정 후 계산')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '확정 진입일' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '확정 진입가' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '가상 투입금액' })).toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: '목표금액' })).not.toBeInTheDocument()
    expect(screen.queryByText('진입가 N/A')).not.toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '뉴스 근거' })).toBeInTheDocument()
    expect(screen.getAllByText('NVDA').length).toBeGreaterThan(0)
    expect(screen.getByText('손절 $110 · 익절 $142')).toBeInTheDocument()
  })

  it('renders fallback news evidence when candidate diagnostics are missing', () => {
    const payload = makePayload()
    const candidate = payload.presets.balanced.entry_candidates[0]
    delete candidate.news_evidence

    render(<StrategySimulatorPanel payload={payload} />)

    expect(screen.getAllByText('뉴스 근거 부족').length).toBeGreaterThan(0)
    expect(screen.getByText('뉴스 근거 데이터 없음')).toBeInTheDocument()
  })

  it('renders a missing-news chip when reason chips contain no valid strings', () => {
    const payload = makePayload()
    const candidate = payload.presets.balanced.entry_candidates[0]
    candidate.news_evidence!.reason_chips = [null, 123, {}] as unknown as string[]

    render(<StrategySimulatorPanel payload={payload} />)

    const entrySection = screen.getByRole('region', { name: '오늘 진입 후보' })
    const rklbCard = within(entrySection).getAllByText('RKLB')[0].closest('.strategy-entry-candidate-card')
    expect(rklbCard).not.toBeNull()
    const newsBlock = within(rklbCard as HTMLElement)
      .getByText('뉴스 근거 강함')
      .closest('.strategy-entry-candidate-news')
    expect(newsBlock).not.toBeNull()
    expect(within(newsBlock as HTMLElement).getByText('뉴스 근거 데이터 없음')).toBeInTheDocument()
  })

  it('separates current entry candidates from historical performance and trade details', () => {
    render(<StrategySimulatorPanel payload={makePayload()} />)

    const entrySection = screen.getByRole('region', { name: '오늘 진입 후보' })
    expect(
      within(entrySection).getByText('현재 신호 기준으로 다음 거래일 open에 확인할 후보입니다.'),
    ).toBeInTheDocument()
    expect(within(entrySection).getByRole('heading', { name: '진입 후보 Top 3' })).toBeInTheDocument()
    expect(within(entrySection).getByRole('heading', { name: '진입 후보 상세' })).toBeInTheDocument()
    expect(within(entrySection).queryByRole('heading', { name: '가상 계좌 가치 변화' })).not.toBeInTheDocument()

    const performanceSection = screen.getByRole('region', { name: '과거 전략 성과' })
    expect(
      within(performanceSection).getByText('선택한 프리셋을 과거 신호에 적용한 관찰용 결과입니다.'),
    ).toBeInTheDocument()
    expect(within(performanceSection).getAllByText('총 수익률').length).toBeGreaterThan(0)
    expect(within(performanceSection).getByRole('heading', { name: '프리셋 비교' })).toBeInTheDocument()
    expect(within(performanceSection).getByRole('heading', { name: '가상 계좌 가치 변화' })).toBeInTheDocument()
    expect(within(performanceSection).queryByRole('heading', { name: '진입 후보 Top 3' })).not.toBeInTheDocument()

    const tradeSection = screen.getByRole('region', { name: '거래 상세' })
    expect(within(tradeSection).getByRole('heading', { name: '열린 포지션' })).toBeInTheDocument()
    expect(within(tradeSection).getByRole('heading', { name: '최근 닫힌 거래' })).toBeInTheDocument()
    expect(within(tradeSection).getByRole('heading', { name: '스킵된 진입' })).toBeInTheDocument()
    expect(within(tradeSection).getByRole('heading', { name: 'LLM 방향 진단' })).toBeInTheDocument()
  })

  it('renders news shadow strategy metrics as read-only performance context', () => {
    render(<StrategySimulatorPanel payload={makePayload()} />)

    const newsShadowSection = screen.getByRole('region', { name: '뉴스 Shadow 성과' })
    expect(within(newsShadowSection).getByText('강한 뉴스 + LLM 강세')).toBeInTheDocument()
    expect(within(newsShadowSection).getByText('표본 1건')).toBeInTheDocument()
    expect(within(newsShadowSection).getByText('5D 평균 +5.00%')).toBeInTheDocument()
    expect(within(newsShadowSection).getByText('20D 완료 0/1')).toBeInTheDocument()
  })

  it('renders today action queue before entry candidates', () => {
    render(<StrategySimulatorPanel payload={makePayload()} />)

    const queueSection = screen.getByRole('region', { name: '오늘 행동 큐' })
    expect(within(queueSection).getAllByText('진입 검토').length).toBeGreaterThan(0)
    expect(within(queueSection).getAllByText('보류').length).toBeGreaterThan(0)
    expect(within(queueSection).getAllByText('제외').length).toBeGreaterThan(0)
    expect(within(queueSection).getAllByText('보유 관리').length).toBeGreaterThan(0)
    expect(within(queueSection).getByText('RKLB')).toBeInTheDocument()
    expect(within(queueSection).getByText('88.5점')).toBeInTheDocument()
    expect(within(queueSection).getByText('다음 거래일 open 기준 진입 조건을 확인할 수 있는 후보입니다.')).toBeInTheDocument()
    expect(within(queueSection).getByText('뉴스 강함')).toBeInTheDocument()
    expect(within(queueSection).getByText('AMD')).toBeInTheDocument()

    const regions = screen.getAllByRole('region').map((region) => region.getAttribute('aria-labelledby') ?? '')
    expect(regions.indexOf('strategy-simulator-today-action-queue')).toBeLessThan(
      regions.indexOf('strategy-simulator-entry-candidates'),
    )
    expect(regions.indexOf('strategy-simulator-entry-candidates')).toBeLessThan(
      regions.indexOf('strategy-simulator-news-shadow'),
    )
    expect(regions.indexOf('strategy-simulator-news-shadow')).toBeLessThan(
      regions.indexOf('strategy-simulator-performance'),
    )
    expect(regions.indexOf('strategy-simulator-performance')).toBeLessThan(
      regions.indexOf('strategy-simulator-trade-details'),
    )
  })

  it('renders today action queue empty state safely', () => {
    const payload = makePayload()
    payload.today_action_queue = {
      status: 'ok',
      as_of: '2026-04-03',
      basis: 'final_action',
      preset_key: 'balanced',
      preset_label: '균형형',
      summary: {
        enter_count: 0,
        watch_count: 0,
        skip_count: 0,
        hold_count: 0,
        top_action: 'none',
      },
      items: [],
      position_alerts: [],
      notes: ['오늘 행동 큐는 관찰용 화면입니다.'],
    }

    render(<StrategySimulatorPanel payload={payload} />)

    const queueSection = screen.getByRole('region', { name: '오늘 행동 큐' })
    expect(within(queueSection).getByText('오늘 확인할 진입 후보나 보유 관리 알림이 없습니다.')).toBeInTheDocument()
  })

  it('renders compact insufficient-data state', () => {
    render(
      <StrategySimulatorPanel
        payload={{
          ...makePayload(),
          status: 'insufficient_data',
          presets: {},
          notes: ['No usable signal or price rows are available for strategy simulation.'],
        }}
      />,
    )

    expect(
      screen.getByText('전략 시뮬레이터를 계산할 데이터가 아직 충분하지 않습니다.'),
    ).toBeInTheDocument()
  })

  it('stays hidden when payload is absent', () => {
    const { container } = render(<StrategySimulatorPanel payload={null} />)

    expect(container).toBeEmptyDOMElement()
  })
})
