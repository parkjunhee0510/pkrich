import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EquityCurveChart } from '../components/EquityCurveChart'
import { ErrorState } from '../components/ErrorState'
import { PortfolioRiskPanel } from '../components/PortfolioRiskPanel'
import { TablePageSkeleton } from '../components/Skeleton'
import { useDashboardData } from '../hooks/useDashboardData'
import { useLocalPortfolioEditor } from '../hooks/useLocalPortfolioEditor'
import type { DailyEntry, PortfolioHoldingInput, PortfolioPosition, PortfolioSummaryData } from '../types'
import { changeColor, parseNumericChange } from '../utils/format'

type PortfolioViewMode = 'summary' | 'edit'
type ToastTone = 'success' | 'error' | 'info'

type ToastItem = {
  id: number
  tone: ToastTone
  message: string
}

type AggregatedHolding = {
  ticker: string
  totalShares: number
  weightedAvgCost: number
  currency: string
  lotCount: number
}

function formatMoney(value: number | null | undefined, currency = 'USD'): string {
  if (value == null) return '-'
  const symbol = currency === 'KRW' ? '₩' : '$'
  return `${symbol}${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function pnlColor(value: number | null | undefined): string {
  if ((value ?? 0) > 0) return 'var(--color-up)'
  if ((value ?? 0) < 0) return 'var(--color-down)'
  return 'var(--color-neutral)'
}

function createEmptyHolding(): PortfolioHoldingInput {
  return {
    ticker: '',
    shares: 1,
    avg_cost: 0,
    currency: 'USD',
  }
}

export function Portfolio() {
  const { data, loading, error, refresh } = useDashboardData()
  const [viewMode, setViewMode] = useState<PortfolioViewMode>('summary')
  const [draftHoldings, setDraftHoldings] = useState<PortfolioHoldingInput[]>([])
  const [expandedTickers, setExpandedTickers] = useState<Record<string, boolean>>({})
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const {
    status: portfolioStatus,
    loading: portfolioLoading,
    saving,
    refresh: refreshPortfolio,
    saveHoldings,
  } = useLocalPortfolioEditor({
    onSaved: () => {
      refresh()
      void refreshPortfolio()
    },
  })

  const latestDay: DailyEntry =
    data && data.days.length > 0
      ? data.days[data.days.length - 1]
      : { date: '', market_overview: [], tickers: [], portfolio_summary: null, portfolio_risk: null }
  const portfolio = latestDay.portfolio_summary as PortfolioSummaryData | null | undefined
  const aggregatedDraft = useMemo(() => aggregateHoldings(draftHoldings), [draftHoldings])
  const sortedPositions = useMemo(
    () =>
      [...(portfolio?.positions ?? [])].sort(
        (a, b) => Math.abs((b.unrealized_pnl ?? 0)) - Math.abs((a.unrealized_pnl ?? 0)),
      ),
    [portfolio?.positions],
  )
  const winCount = portfolio?.positions.filter((position) => (position.unrealized_pnl ?? 0) > 0).length ?? 0
  const lossCount = portfolio?.positions.filter((position) => (position.unrealized_pnl ?? 0) < 0).length ?? 0

  function pushToast(tone: ToastTone, message: string) {
    const id = Date.now() + Math.floor(Math.random() * 1000)
    setToasts((current) => [...current, { id, tone, message }])
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id))
    }, 3200)
  }

  useEffect(() => {
    document.title = '포트폴리오 · Stock Research'
  }, [])

  if (loading || portfolioLoading) return <TablePageSkeleton title="포트폴리오" />
  if (error) return <ErrorState message={error} />
  if (!data || data.days.length === 0) return <p className="status">No data available.</p>

  async function handleSave() {
    const validationError = validateDraftHoldings(draftHoldings)
    if (validationError) {
      pushToast('error', validationError)
      return
    }

    const result = await saveHoldings(draftHoldings)
    if (!result.ok) {
      pushToast('error', result.message)
      return
    }

    pushToast('success', '포트폴리오를 저장했습니다. 리서치 실행은 대시보드 자동화에서 계속 수동으로 진행할 수 있습니다.')
    setViewMode('summary')
  }

  function handleCancel() {
    setDraftHoldings(portfolioStatus.holdings)
    setViewMode('summary')
    pushToast('info', '편집 중인 변경을 취소하고 마지막 저장 상태로 되돌렸습니다.')
  }

  return (
    <div className="portfolio-page">
      {toasts.length > 0 && (
        <div className="dashboard-toast-stack" aria-live="polite" aria-atomic="true">
          {toasts.map((toast) => (
            <div key={toast.id} className={`dashboard-toast dashboard-toast-${toast.tone}`}>
              {toast.message}
            </div>
          ))}
        </div>
      )}

      <div className="dashboard-header">
        <h2>포트폴리오 · {latestDay.date}</h2>
        <div className="portfolio-mode-row">
          <button
            type="button"
            className={`preset-chip ${viewMode === 'summary' ? 'active' : ''}`}
            onClick={() => setViewMode('summary')}
          >
            요약 보기
          </button>
          <button
            type="button"
            className={`preset-chip ${viewMode === 'edit' ? 'active' : ''}`}
            onClick={() => {
              setDraftHoldings(portfolioStatus.holdings)
              setViewMode('edit')
            }}
          >
            포트폴리오 편집
          </button>
        </div>
      </div>

      <div className={`portfolio-editor-status stage-${portfolioStatus.stage}`}>
        <span className="dashboard-automation-stage">{portfolioStatus.stageLabel}</span>
        <p>{portfolioStatus.message}</p>
      </div>

      {viewMode === 'summary' ? (
        <>
          {!portfolio || !portfolio.positions || portfolio.positions.length === 0 ? (
            <div className="dashboard-empty-state">
              <strong>포트폴리오 데이터가 없습니다.</strong>
              <p>편집 모드에서 첫 lot를 추가한 뒤 저장하면 이후 요약과 손익 계산이 여기에 반영됩니다.</p>
            </div>
          ) : (
            <>
              <div className="portfolio-summary-grid">
                <SummaryCard label="평가 금액" value={formatMoney(portfolio.total_market_value)} />
                <SummaryCard label="투자 원금" value={formatMoney(portfolio.total_cost_basis)} />
                <SummaryCard
                  label="미실현 손익"
                  value={`${(portfolio.total_unrealized_pnl ?? 0) >= 0 ? '+' : ''}${formatMoney(portfolio.total_unrealized_pnl)}`}
                  sub={`${(portfolio.total_unrealized_return_pct ?? 0) >= 0 ? '+' : ''}${(portfolio.total_unrealized_return_pct ?? 0).toFixed(2)}%`}
                  tone={pnlColor(portfolio.total_unrealized_pnl)}
                />
                <SummaryCard label="승패" value={`${winCount}W / ${lossCount}L`} tone="var(--color-text)" />
              </div>

              <EquityCurveChart days={data.days} />

              <PortfolioRiskPanel risk={latestDay.portfolio_risk} />

              <div className="table-wrap">
                <table className="watchlist-table">
                  <thead>
                    <tr>
                      <th>종목</th>
                      <th style={{ textAlign: 'right' }}>수량</th>
                      <th style={{ textAlign: 'right' }}>평균단가</th>
                      <th style={{ textAlign: 'right' }}>현재가</th>
                      <th style={{ textAlign: 'right' }}>평가금액</th>
                      <th style={{ textAlign: 'right' }}>손익</th>
                      <th style={{ textAlign: 'right' }}>수익률</th>
                      <th>시그널</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedPositions.map((position) => (
                      <SummaryRow
                        key={`${position.ticker}-${position.avg_cost}-${position.shares}`}
                        position={position}
                        latestDay={latestDay}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      ) : (
        <div className="portfolio-editor-shell">
          <div className="portfolio-editor-toolbar">
            <div>
              <strong>보유 lot 편집</strong>
              <p>기본 화면은 합산 기준으로 보이고, 각 티커를 펼치면 실제로 저장되는 개별 lot를 수정할 수 있습니다.</p>
            </div>
            <div className="portfolio-editor-actions">
              <button type="button" className="secondary-action-button" onClick={handleCancel} disabled={saving}>
                취소
              </button>
              <button type="button" className="primary-action-button" onClick={handleSave} disabled={saving}>
                {saving ? '저장 중...' : '저장'}
              </button>
            </div>
          </div>

          <div className="portfolio-editor-note">
            저장 후 리서치 재실행은 자동으로 하지 않습니다. 필요하면 대시보드의 `리서치 실행` 버튼을 사용해주세요.
          </div>

          <div className="portfolio-editor-list">
            {aggregatedDraft.map((group) => {
              const expanded = expandedTickers[group.ticker] ?? false
              const indexedLots = draftHoldings
                .map((holding, index) => ({ holding, index }))
                .filter(({ holding }) => holding.ticker === group.ticker)

              return (
                <div key={group.ticker} className="portfolio-group-card">
                  <button
                    type="button"
                    className="portfolio-group-head"
                    onClick={() =>
                      setExpandedTickers((current) => ({
                        ...current,
                        [group.ticker]: !expanded,
                      }))
                    }
                  >
                    <div>
                      <strong>{group.ticker}</strong>
                      <p>
                        {group.totalShares.toLocaleString()}주 · 평균단가 {formatMoney(group.weightedAvgCost, group.currency)} · {group.lotCount} lot
                      </p>
                    </div>
                    <span>{expanded ? '접기' : '펼치기'}</span>
                  </button>

                  {expanded ? (
                    <div className="portfolio-lot-list">
                      {indexedLots.map(({ holding, index }) => (
                        <PortfolioLotEditor
                          key={`${group.ticker}-${index}`}
                          holding={holding}
                          onChange={(nextHolding) =>
                            setDraftHoldings((current) =>
                              current.map((entry, entryIndex) => (entryIndex === index ? nextHolding : entry)),
                            )
                          }
                          onDelete={() =>
                            setDraftHoldings((current) => current.filter((_, entryIndex) => entryIndex !== index))
                          }
                        />
                      ))}

                      <button
                        type="button"
                        className="portfolio-add-lot-button"
                        onClick={() =>
                          setDraftHoldings((current) => [
                            ...current,
                            { ...createEmptyHolding(), ticker: group.ticker, currency: indexedLots[0]?.holding.currency ?? 'USD' },
                          ])
                        }
                      >
                        + {group.ticker} lot 추가
                      </button>
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>

          <button
            type="button"
            className="portfolio-add-lot-button standalone"
            onClick={() => setDraftHoldings((current) => [...current, createEmptyHolding()])}
          >
            + 새 보유 lot 추가
          </button>
        </div>
      )}
    </div>
  )
}

function SummaryCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string
  value: string
  sub?: string
  tone?: string
}) {
  return (
    <div className="portfolio-summary-card">
      <div className="portfolio-card-label">{label}</div>
      <div className="portfolio-card-value" style={tone ? { color: tone } : undefined}>
        {value}
      </div>
      {sub ? (
        <div className="portfolio-card-sub" style={tone ? { color: tone } : undefined}>
          {sub}
        </div>
      ) : null}
    </div>
  )
}

function SummaryRow({
  position,
  latestDay,
}: {
  position: PortfolioPosition
  latestDay: DailyEntry
}) {
  const tickerAnalysis = latestDay.tickers.find((ticker) => ticker.ticker === position.ticker)
  const dailyChange = tickerAnalysis ? parseNumericChange(tickerAnalysis.data_snapshot['Daily Change'] ?? '0') : null

  return (
    <tr>
      <td>
        <Link to={`/ticker/${position.ticker}`} className="ticker-link">
          {position.ticker}
        </Link>
      </td>
      <td style={{ textAlign: 'right' }}>{position.shares}</td>
      <td style={{ textAlign: 'right' }}>{formatMoney(position.avg_cost, position.currency)}</td>
      <td style={{ textAlign: 'right' }}>
        <span>{formatMoney(position.market_price, position.currency)}</span>
        {dailyChange !== null ? (
          <span style={{ color: changeColor(dailyChange), fontSize: '0.8rem', marginLeft: '0.4rem' }}>
            {dailyChange >= 0 ? '+' : ''}
            {dailyChange.toFixed(2)}%
          </span>
        ) : null}
      </td>
      <td style={{ textAlign: 'right' }}>{formatMoney(position.market_value, position.currency)}</td>
      <td style={{ textAlign: 'right', color: pnlColor(position.unrealized_pnl) }}>
        {(position.unrealized_pnl ?? 0) >= 0 ? '+' : ''}
        {formatMoney(position.unrealized_pnl, position.currency)}
      </td>
      <td style={{ textAlign: 'right', color: pnlColor(position.unrealized_return_pct) }}>
        {(position.unrealized_return_pct ?? 0) >= 0 ? '+' : ''}
        {(position.unrealized_return_pct ?? 0).toFixed(2)}%
      </td>
      <td className="takeaway-cell">{tickerAnalysis?.signal_or_takeaway ?? '-'}</td>
    </tr>
  )
}

function PortfolioLotEditor({
  holding,
  onChange,
  onDelete,
}: {
  holding: PortfolioHoldingInput
  onChange: (holding: PortfolioHoldingInput) => void
  onDelete: () => void
}) {
  return (
    <div className="portfolio-lot-editor">
      <input
        type="text"
        value={holding.ticker}
        placeholder="TICKER"
        onChange={(event) => onChange({ ...holding, ticker: event.target.value.toUpperCase() })}
      />
      <input
        type="number"
        min={0.0001}
        step={0.01}
        value={holding.shares}
        onChange={(event) => onChange({ ...holding, shares: Number(event.target.value) })}
      />
      <input
        type="number"
        min={0}
        step={0.01}
        value={holding.avg_cost}
        onChange={(event) => onChange({ ...holding, avg_cost: Number(event.target.value) })}
      />
      <select value={holding.currency} onChange={(event) => onChange({ ...holding, currency: event.target.value })}>
        <option value="USD">USD</option>
        <option value="KRW">KRW</option>
      </select>
      <button type="button" className="portfolio-delete-lot-button" onClick={onDelete}>
        삭제
      </button>
    </div>
  )
}

function aggregateHoldings(holdings: PortfolioHoldingInput[]): AggregatedHolding[] {
  const grouped = new Map<string, AggregatedHolding>()

  for (const holding of holdings) {
    const ticker = holding.ticker || 'NEW'
    const current = grouped.get(ticker)
    if (!current) {
      grouped.set(ticker, {
        ticker,
        totalShares: holding.shares || 0,
        weightedAvgCost: holding.avg_cost || 0,
        currency: holding.currency || 'USD',
        lotCount: 1,
      })
      continue
    }

    const nextTotalShares = current.totalShares + (holding.shares || 0)
    const nextCostValue =
      current.weightedAvgCost * current.totalShares + (holding.avg_cost || 0) * (holding.shares || 0)
    grouped.set(ticker, {
      ticker,
      totalShares: nextTotalShares,
      weightedAvgCost: nextTotalShares > 0 ? nextCostValue / nextTotalShares : 0,
      currency: current.currency,
      lotCount: current.lotCount + 1,
    })
  }

  return [...grouped.values()].sort((left, right) => left.ticker.localeCompare(right.ticker))
}

function validateDraftHoldings(holdings: PortfolioHoldingInput[]): string | null {
  if (holdings.length === 0) {
    return '최소 1개 이상의 보유 lot를 남겨주세요.'
  }

  for (const holding of holdings) {
    if (!/^[A-Z][A-Z0-9.-]{0,14}$/.test(holding.ticker.trim().toUpperCase())) {
      return `유효하지 않은 티커가 있습니다: ${holding.ticker || '(빈 값)'}`
    }
    if (!Number.isFinite(holding.shares) || holding.shares <= 0) {
      return `${holding.ticker}: 수량은 0보다 커야 합니다.`
    }
    if (!Number.isFinite(holding.avg_cost) || holding.avg_cost < 0) {
      return `${holding.ticker}: 평균단가는 0 이상이어야 합니다.`
    }
  }

  return null
}
