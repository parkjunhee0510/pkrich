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
    expect(screen.getByText('AMD')).toBeInTheDocument()
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
    expect(screen.getAllByText('다음 open 대기').length).toBeGreaterThan(0)
    expect(screen.getAllByText('진입 기준 다음 거래일 open').length).toBeGreaterThan(0)
    expect(screen.getByText('확정 진입가 open 데이터 대기')).toBeInTheDocument()
    expect(screen.getByText('손절/익절 진입가 확정 후 계산')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '확정 진입일' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '확정 진입가' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '가상 투입금액' })).toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: '목표금액' })).not.toBeInTheDocument()
    expect(screen.queryByText('진입가 N/A')).not.toBeInTheDocument()
    expect(screen.getAllByText('NVDA').length).toBeGreaterThan(0)
    expect(screen.getByText('손절 $110 · 익절 $142')).toBeInTheDocument()
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
