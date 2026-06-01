import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type {
  StrategySimulatorEntryCandidate,
  StrategySimulatorEquityPoint,
  StrategySimulatorPayload,
  StrategySimulatorPreset,
  StrategySimulatorRow,
} from '../types'

const PRESET_ORDER = ['conservative', 'balanced', 'aggressive']
const DIAGNOSTIC_ORDER = ['aligned', 'conflict', 'missing']
const CANDIDATE_STATUS_PRIORITY: Record<string, number> = {
  entry_ready: 0,
  pending_next_open: 1,
  already_held: 2,
  insufficient_cash: 3,
  max_positions_reached: 4,
  missing_entry_price: 5,
  simulated_entry_closed: 6,
}

export function StrategySimulatorPanel({
  payload,
}: {
  payload?: StrategySimulatorPayload | null
}) {
  const [selectedKey, setSelectedKey] = useState('balanced')

  const presetKeys = useMemo(
    () => PRESET_ORDER.filter((key) => Boolean(payload?.presets?.[key])),
    [payload],
  )

  if (!payload) return null

  if (payload.status !== 'ok') {
    return (
      <section className="signals-meta-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>전략 시뮬레이터</h3>
            <p className="section-kicker">
              전략 시뮬레이터를 계산할 데이터가 아직 충분하지 않습니다.
            </p>
          </div>
        </div>
      </section>
    )
  }

  const effectiveSelectedKey = presetKeys.includes(selectedKey)
    ? selectedKey
    : (presetKeys[0] ?? '')
  const selected = payload.presets[effectiveSelectedKey]

  if (!selected) return null

  return (
    <section className="signals-meta-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>전략 시뮬레이터</h3>
          <p className="section-kicker">
            {payload.as_of || 'N/A'} · {payload.basis}
          </p>
        </div>
        <span className="period-badge ap-mode-badge">{payload.mode}</span>
      </div>

      <div className="signal-summary-row u-mt-3" role="group" aria-label="전략 프리셋">
        {presetKeys.map((key) => {
          const preset = payload.presets[key]
          return (
            <button
              key={key}
              type="button"
              className="period-badge ap-mode-badge"
              aria-pressed={key === effectiveSelectedKey}
              onClick={() => setSelectedKey(key)}
            >
              {preset.label}
            </button>
          )
        })}
      </div>

      <StrategySimulatorSection
        headingId="strategy-simulator-entry-candidates"
        title="오늘 진입 후보"
        description="현재 신호 기준으로 다음 거래일 open에 확인할 후보입니다."
      >
        {renderEntryCandidateCards(selected)}
        {renderEntryCandidateTable(selected)}
      </StrategySimulatorSection>

      <StrategySimulatorSection
        headingId="strategy-simulator-performance"
        title="과거 전략 성과"
        description="선택한 프리셋을 과거 신호에 적용한 관찰용 결과입니다."
      >
        <div className="signal-summary-grid">
          <SummaryMetricCard
            label="총 수익률"
            value={formatPercent(selected.summary.total_return_pct)}
            note={selected.label}
          />
          <SummaryMetricCard
            label="실현 손익"
            value={formatCurrency(selected.summary.realized_pnl)}
            note={`닫힌 거래 ${formatInteger(selected.summary.closed_trade_count)}건`}
          />
          <SummaryMetricCard
            label="미실현 손익"
            value={formatCurrency(selected.summary.unrealized_pnl)}
            note={`열린 포지션 ${formatInteger(selected.summary.open_position_count)}건`}
          />
          <SummaryMetricCard
            label="최대 낙폭"
            value={formatPercent(selected.summary.max_drawdown_pct)}
            note={`승률 ${formatRatio(selected.summary.win_rate)}`}
          />
        </div>

        <h4 className="ap-table-heading">프리셋 비교</h4>
        <div className="watchlist-table-shell">
          <table className="watchlist-table ap-table">
            <thead>
              <tr>
                <th>프리셋</th>
                <th className="ap-num">비중</th>
                <th className="ap-num">최대</th>
                <th className="ap-num">손절</th>
                <th className="ap-num">익절</th>
                <th className="ap-num">총 수익률</th>
                <th className="ap-num">열린 포지션</th>
              </tr>
            </thead>
            <tbody>
              {presetKeys.map((key) => {
                const preset = payload.presets[key]
                return (
                  <tr key={key}>
                    <td className="ap-ticker">{preset.label}</td>
                    <td className="ap-num">{formatParamPercent(preset.params.position_size_pct)}</td>
                    <td className="ap-num">{formatInteger(preset.params.max_positions)}</td>
                    <td className="ap-num">{formatParamPercent(preset.params.stop_loss_pct)}</td>
                    <td className="ap-num">{formatParamPercent(preset.params.take_profit_pct)}</td>
                    <td className="ap-num">{formatPercent(preset.summary.total_return_pct)}</td>
                    <td className="ap-num">{formatInteger(preset.summary.open_position_count)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <EquitySparkline points={selected.equity_curve} />
      </StrategySimulatorSection>

      <StrategySimulatorSection
        headingId="strategy-simulator-trade-details"
        title="거래 상세"
        description="열린 포지션, 닫힌 거래, 스킵 사유, LLM 방향 진단을 확인합니다."
      >
        {renderOpenPositions(selected)}
        {renderTrades(selected)}
        {renderSkippedEntries(selected)}
        {renderDiagnostics(selected)}
      </StrategySimulatorSection>

      <p className="section-kicker ap-footnote">
        관찰용 과거 시뮬레이션이며 공식 추천, 포트폴리오 상태, 매매 실행 로직을 변경하지 않습니다.
      </p>
    </section>
  )
}

function StrategySimulatorSection({
  headingId,
  title,
  description,
  children,
}: {
  headingId: string
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <section className="strategy-simulator-section" aria-labelledby={headingId}>
      <div className="strategy-simulator-section-header">
        <div>
          <h4 id={headingId} className="strategy-simulator-section-title">{title}</h4>
          <p className="section-kicker">{description}</p>
        </div>
      </div>
      <div className="strategy-simulator-section-body">{children}</div>
    </section>
  )
}

function renderEntryCandidateCards(preset: StrategySimulatorPreset) {
  const candidates = topEntryCandidates(preset.entry_candidates ?? [])

  return (
    <>
      <h4 className="ap-table-heading">진입 후보 Top 3</h4>
      <div className="strategy-entry-candidate-grid">
        {candidates.length > 0 ? (
          candidates.map((candidate) => (
            <div
              key={`${candidate.rank}-${candidate.ticker}-${candidate.status}`}
              className={`strategy-entry-candidate-card strategy-entry-candidate-${candidateTone(candidate.status)}`}
            >
              <div className="strategy-entry-candidate-head">
                <span className="strategy-entry-candidate-rank">#{formatInteger(candidate.rank)}</span>
                <span className="strategy-entry-candidate-status">{candidate.status_label || candidate.status}</span>
              </div>
              <div className="strategy-entry-candidate-ticker">{candidate.ticker || 'N/A'}</div>
              <div className="strategy-entry-candidate-reason">{candidate.reason || 'N/A'}</div>
              <div className="strategy-entry-candidate-metrics">
                <span>신호일 {candidate.signal_date || 'N/A'}</span>
                <span>확신도 {formatConviction(candidate.conviction)}</span>
                <span>진입 기준 {formatEntryBasis(candidate)}</span>
                <span>확정 진입가 {formatConfirmedEntryPrice(candidate)}</span>
                <span>{formatCandidateRisk(candidate)}</span>
              </div>
            </div>
          ))
        ) : (
          <div className="strategy-entry-candidate-empty">후보 없음</div>
        )}
      </div>
    </>
  )
}

function renderEntryCandidateTable(preset: StrategySimulatorPreset) {
  const candidates = preset.entry_candidates ?? []

  return (
    <>
      <h4 className="ap-table-heading">진입 후보 상세</h4>
      <div className="watchlist-table-shell strategy-entry-candidate-table-shell">
        <table className="watchlist-table ap-table strategy-entry-candidate-table">
          <thead>
            <tr>
              <th className="ap-num">순위</th>
              <th>티커</th>
              <th>상태</th>
              <th>신호일</th>
              <th>진입 기준</th>
              <th className="ap-num">확신도</th>
              <th>확정 진입일</th>
              <th className="ap-num">확정 진입가</th>
              <th className="ap-num">손절</th>
              <th className="ap-num">익절</th>
              <th className="ap-num">가상 투입금액</th>
              <th>LLM</th>
            </tr>
          </thead>
          <tbody>
            {candidates.length > 0 ? (
              candidates.map((candidate) => (
                <tr key={`${candidate.rank}-${candidate.ticker}-${candidate.signal_date}`}>
                  <td className="ap-num">{formatInteger(candidate.rank)}</td>
                  <td className="ap-ticker">{candidate.ticker || 'N/A'}</td>
                  <td>{candidate.status_label || candidate.status || 'N/A'}</td>
                  <td>{candidate.signal_date || 'N/A'}</td>
                  <td>{formatEntryBasis(candidate)}</td>
                  <td className="ap-num">{formatConviction(candidate.conviction)}</td>
                  <td>{formatConfirmedEntryDate(candidate)}</td>
                  <td className="ap-num">{formatConfirmedEntryPrice(candidate)}</td>
                  <td className="ap-num">{formatRiskPrice(candidate.stop_price, candidate)}</td>
                  <td className="ap-num">{formatRiskPrice(candidate.take_profit_price, candidate)}</td>
                  <td className="ap-num">{formatPrice(candidate.target_notional)}</td>
                  <td>{candidate.llm_alignment || 'N/A'}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={12}>후보 없음</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}

function topEntryCandidates(candidates: StrategySimulatorEntryCandidate[]) {
  return [...candidates]
    .sort((a, b) => (
      candidateStatusPriority(a.status) - candidateStatusPriority(b.status)
      || (a.rank ?? 999) - (b.rank ?? 999)
      || (b.conviction ?? -1) - (a.conviction ?? -1)
      || (a.ticker || '').localeCompare(b.ticker || '')
    ))
    .slice(0, 3)
}

function candidateStatusPriority(status: string): number {
  return CANDIDATE_STATUS_PRIORITY[status] ?? 99
}

function candidateTone(status: string): string {
  if (status === 'entry_ready') return 'ready'
  if (status === 'pending_next_open') return 'pending'
  if (status === 'already_held') return 'held'
  if (status === 'simulated_entry_closed') return 'muted'
  return 'blocked'
}

function formatEntryBasis(_candidate: StrategySimulatorEntryCandidate): string {
  return '다음 거래일 open'
}

function formatConfirmedEntryDate(candidate: StrategySimulatorEntryCandidate): string {
  if (candidate.entry_date) return candidate.entry_date
  if (isOpenDataPending(candidate)) return 'open 데이터 대기'
  return 'N/A'
}

function formatConfirmedEntryPrice(candidate: StrategySimulatorEntryCandidate): string {
  if (candidate.entry_price !== null && candidate.entry_price !== undefined) {
    return formatPrice(candidate.entry_price)
  }
  if (isOpenDataPending(candidate)) return 'open 데이터 대기'
  return 'N/A'
}

function formatRiskPrice(value: number | null | undefined, candidate: StrategySimulatorEntryCandidate): string {
  if (value !== null && value !== undefined) return formatPrice(value)
  if (isOpenDataPending(candidate)) return '확정 후 계산'
  return 'N/A'
}

function formatCandidateRisk(candidate: StrategySimulatorEntryCandidate): string {
  if (
    isOpenDataPending(candidate)
    && candidate.stop_price === null
    && candidate.take_profit_price === null
  ) {
    return '손절/익절 진입가 확정 후 계산'
  }
  return `손절 ${formatPrice(candidate.stop_price)} · 익절 ${formatPrice(candidate.take_profit_price)}`
}

function isOpenDataPending(candidate: StrategySimulatorEntryCandidate): boolean {
  return candidate.status === 'pending_next_open' || candidate.status === 'missing_entry_price'
}

function SummaryMetricCard({
  label,
  value,
  note,
}: {
  label: string
  value: string
  note: string
}) {
  return (
    <div className="signal-summary-card ap-summary-card">
      <div className="signal-summary-direction">{label}</div>
      <div className="signal-summary-count ap-summary-value">{value}</div>
      <div className="ap-summary-note">{note}</div>
    </div>
  )
}

function EquitySparkline({ points }: { points: StrategySimulatorEquityPoint[] }) {
  const svg = useMemo(() => buildSparkline(points), [points])

  if (!svg) return null

  return (
    <>
      <h4 className="ap-table-heading">가상 계좌 가치 변화</h4>
      <p className="section-kicker">현금 + 열린 포지션 평가액 · 매수/매도 비용 반영</p>
      <svg
        className="performance-svg-chart"
        viewBox={`0 0 ${svg.width} ${svg.height}`}
        role="img"
        aria-label={`가상 계좌 가치 변화 ${svg.startDate}부터 ${svg.endDate}까지`}
      >
        <title>가상 계좌 가치 변화</title>
        <desc>{`${svg.startDate}부터 ${svg.endDate}까지 가상 계좌 가치 ${formatPrice(svg.lastEquity)}`}</desc>
        {svg.grid.map((line) => (
          <g key={line.value}>
            <line className="performance-svg-grid" x1={42} x2={svg.width - 16} y1={line.y} y2={line.y} />
            <text className="performance-svg-axis" x={36} y={line.y + 4} textAnchor="end">
              {formatAxisCurrency(line.value)}
            </text>
          </g>
        ))}
        <polyline className="performance-svg-line" points={svg.points} fill="none" stroke="var(--ink)" strokeWidth="3" />
        <text className="performance-svg-axis" x={42} y={svg.height - 8}>
          {svg.startDate}
        </text>
        <text className="performance-svg-axis" x={svg.width - 16} y={svg.height - 8} textAnchor="end">
          {svg.endDate}
        </text>
      </svg>
    </>
  )
}

function renderOpenPositions(preset: StrategySimulatorPreset) {
  return (
    <>
      <h4 className="ap-table-heading">열린 포지션</h4>
      <RowsTable
        rows={preset.open_positions}
        emptyText="열린 포지션이 없습니다."
        columns={[
          { label: '티커', render: (row) => stringValue(row.ticker), className: 'ap-ticker' },
          { label: '진입일', render: (row) => stringValue(row.entry_date) },
          { label: '최근일', render: (row) => stringValue(row.latest_date) },
          { label: '수익률', render: (row) => formatPercent(asNumber(row.return_pct)), className: 'ap-num' },
          { label: '미실현 손익', render: (row) => formatCurrency(asNumber(row.unrealized_pnl)), className: 'ap-num' },
          { label: 'LLM', render: (row) => stringValue(row.llm_alignment) },
        ]}
      />
    </>
  )
}

function renderTrades(preset: StrategySimulatorPreset) {
  return (
    <>
      <h4 className="ap-table-heading">최근 닫힌 거래</h4>
      <RowsTable
        rows={preset.trades.slice(-8).reverse()}
        emptyText="닫힌 거래가 없습니다."
        columns={[
          { label: '티커', render: (row) => stringValue(row.ticker), className: 'ap-ticker' },
          { label: '진입일', render: (row) => stringValue(row.entry_date) },
          { label: '청산일', render: (row) => stringValue(row.exit_date) },
          { label: '사유', render: (row) => stringValue(row.exit_reason) },
          { label: '수익률', render: (row) => formatPercent(asNumber(row.return_pct)), className: 'ap-num' },
          { label: '실현 손익', render: (row) => formatCurrency(asNumber(row.realized_pnl)), className: 'ap-num' },
        ]}
      />
    </>
  )
}

function renderSkippedEntries(preset: StrategySimulatorPreset) {
  const reasons = Object.entries(preset.skipped_entries.by_reason ?? {})
  return (
    <>
      <h4 className="ap-table-heading">스킵된 진입</h4>
      <div className="watchlist-table-shell">
        <table className="watchlist-table ap-table">
          <thead>
            <tr>
              <th>사유</th>
              <th className="ap-num">건수</th>
            </tr>
          </thead>
          <tbody>
            {reasons.length > 0 ? (
              reasons.map(([reason, count]) => (
                <tr key={reason}>
                  <td>{reason}</td>
                  <td className="ap-num">{formatInteger(count)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td>없음</td>
                <td className="ap-num">0</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}

function renderDiagnostics(preset: StrategySimulatorPreset) {
  return (
    <>
      <h4 className="ap-table-heading">LLM 방향 진단</h4>
      <div className="watchlist-table-shell">
        <table className="watchlist-table ap-table">
          <thead>
            <tr>
              <th>구분</th>
              <th className="ap-num">전체</th>
              <th className="ap-num">닫힌 거래</th>
              <th className="ap-num">실현 손익</th>
              <th className="ap-num">미실현 손익</th>
              <th className="ap-num">평균 수익률</th>
              <th className="ap-num">승률</th>
            </tr>
          </thead>
          <tbody>
            {DIAGNOSTIC_ORDER.map((key) => {
              const row = preset.llm_direction_diagnostics[key]
              return (
                <tr key={key}>
                  <td className="ap-ticker">{key}</td>
                  <td className="ap-num">{formatInteger(row?.trade_count)}</td>
                  <td className="ap-num">{formatInteger(row?.closed_trade_count)}</td>
                  <td className="ap-num">{formatCurrency(row?.realized_pnl)}</td>
                  <td className="ap-num">{formatCurrency(row?.unrealized_pnl)}</td>
                  <td className="ap-num">{formatPercent(row?.avg_trade_return_pct)}</td>
                  <td className="ap-num">{formatRatio(row?.win_rate)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}

function RowsTable({
  rows,
  columns,
  emptyText,
}: {
  rows: StrategySimulatorRow[]
  columns: Array<{
    label: string
    className?: string
    render: (row: StrategySimulatorRow) => string
  }>
  emptyText: string
}) {
  return (
    <div className="watchlist-table-shell">
      <table className="watchlist-table ap-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.label} className={column.className}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length > 0 ? (
            rows.map((row, index) => (
              <tr key={`${stringValue(row.ticker)}-${index}`}>
                {columns.map((column) => (
                  <td key={column.label} className={column.className}>
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={columns.length}>{emptyText}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function buildSparkline(points: StrategySimulatorEquityPoint[]) {
  const normalized = points
    .filter((point) => typeof point.equity === 'number' && point.date)
    .map((point) => ({ date: point.date, equity: point.equity }))

  if (normalized.length < 2) return null

  const width = 640
  const height = 170
  const left = 42
  const right = 16
  const top = 14
  const bottom = 28
  const values = normalized.map((point) => point.equity)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || Math.max(1, max)
  const plotWidth = width - left - right
  const plotHeight = height - top - bottom
  const yFor = (value: number) => top + ((max - value) / range) * plotHeight
  const xStep = plotWidth / Math.max(1, normalized.length - 1)
  const polyline = normalized
    .map((point, index) => `${(left + index * xStep).toFixed(1)},${yFor(point.equity).toFixed(1)}`)
    .join(' ')
  const grid = [0, 0.5, 1].map((ratio) => {
    const value = max - range * ratio
    return { value, y: yFor(value) }
  })

  return {
    width,
    height,
    points: polyline,
    grid,
    startDate: normalized[0].date,
    endDate: normalized[normalized.length - 1].date,
    lastEquity: normalized[normalized.length - 1].equity,
  }
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function stringValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'N/A'
  return String(value)
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function formatParamPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  const percentage = Math.abs(value) <= 1 ? value * 100 : value
  const sign = percentage > 0 ? '+' : ''
  return `${sign}${percentage.toFixed(0)}%`
}

function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return `${(value * 100).toFixed(1)}%`
}

function formatConviction(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return value.toFixed(0)
}

function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  const sign = value > 0 ? '+' : value < 0 ? '-' : ''
  return `${sign}$${Math.abs(value).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`
}

function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return `$${Math.abs(value).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`
}

function formatAxisCurrency(value: number): string {
  if (Math.abs(value) >= 1000) return `$${(value / 1000).toFixed(0)}k`
  return `$${value.toFixed(0)}`
}

function formatInteger(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return value.toFixed(0)
}
