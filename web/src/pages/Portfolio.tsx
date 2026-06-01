import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EquityCurveChart } from '../components/EquityCurveChart'
import { ErrorState } from '../components/ErrorState'
import { PortfolioCommandCenter } from '../components/PortfolioCommandCenter'
import { PortfolioRiskPanel } from '../components/PortfolioRiskPanel'
import { TablePageSkeleton } from '../components/Skeleton'
import { EmptyState } from '../components/ui/EmptyState'
import { useDashboardData } from '../hooks/useDashboardData'
import { useLocalPortfolioEditor } from '../hooks/useLocalPortfolioEditor'
import type { DailyEntry, PortfolioHoldingInput, PortfolioPosition, PortfolioSummaryData } from '../types'
import { buildPortfolioCommandCenter } from '../utils/portfolioCommandCenter'
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

function prepareInitialDraft(holdings: PortfolioHoldingInput[]): PortfolioHoldingInput[] {
  return holdings.length > 0 ? holdings : [createEmptyHolding()]
}

function countChangedLots(original: PortfolioHoldingInput[], draft: PortfolioHoldingInput[]): number {
  const maxLength = Math.max(original.length, draft.length)
  let changed = 0

  for (let index = 0; index < maxLength; index += 1) {
    if (!sameHolding(original[index], draft[index])) changed += 1
  }

  return changed
}

function sameHolding(left?: PortfolioHoldingInput, right?: PortfolioHoldingInput): boolean {
  if (!left && right && isStarterHolding(right)) return true
  if (!left || !right) return left === right

  return (
    left.ticker === right.ticker &&
    left.shares === right.shares &&
    left.avg_cost === right.avg_cost &&
    left.currency === right.currency
  )
}

function isStarterHolding(holding: PortfolioHoldingInput): boolean {
  return holding.ticker.trim() === '' && holding.shares === 1 && holding.avg_cost === 0 && holding.currency === 'USD'
}

function buildTickerOptions({
  analyses,
  holdings,
  positions,
}: {
  analyses: DailyEntry['tickers']
  holdings: PortfolioHoldingInput[]
  positions: PortfolioPosition[]
}): string[] {
  const options = new Set<string>()

  for (const ticker of analyses) addTickerOption(options, ticker.ticker)
  for (const holding of holdings) addTickerOption(options, holding.ticker)
  for (const position of positions) addTickerOption(options, position.ticker)

  return [...options].sort((left, right) => left.localeCompare(right))
}

function addTickerOption(options: Set<string>, value: string | null | undefined) {
  const ticker = value?.trim().toUpperCase()
  if (ticker) options.add(ticker)
}

function buildCurrentPriceLookup({
  analyses,
  positions,
}: {
  analyses: DailyEntry['tickers']
  positions: PortfolioPosition[]
}): Map<string, number> {
  const lookup = new Map<string, number>()

  for (const ticker of analyses) {
    addCurrentPrice(lookup, ticker.ticker, parsePriceValue(ticker.data_snapshot?.Price))
  }
  for (const position of positions) {
    addCurrentPrice(lookup, position.ticker, position.market_price)
  }

  return lookup
}

function addCurrentPrice(lookup: Map<string, number>, tickerValue: string | null | undefined, priceValue: number | null) {
  const ticker = tickerValue?.trim().toUpperCase()
  if (!ticker || priceValue === null) return
  lookup.set(ticker, priceValue)
}

function parsePriceValue(value: string | number | null | undefined): number | null {
  if (typeof value === 'number') return Number.isFinite(value) && value >= 0 ? value : null
  const match = String(value ?? '').replace(/,/g, '').match(/\d+(?:\.\d+)?/)
  if (!match) return null
  const parsed = Number(match[0])
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null
}

function pricesMatch(left: number, right: number): boolean {
  return Math.abs(left - right) < 0.000001
}

function withDefaultAverageCost(
  holding: PortfolioHoldingInput,
  ticker: string,
  currentPriceByTicker: Map<string, number>,
): PortfolioHoldingInput {
  const currentPrice = currentPriceByTicker.get(ticker)
  const previousTicker = holding.ticker.trim().toUpperCase()
  const previousCurrentPrice = previousTicker ? currentPriceByTicker.get(previousTicker) : undefined
  const hasAverageCost = Number.isFinite(holding.avg_cost) && holding.avg_cost > 0
  const averageCostLooksAutoFilled =
    !hasAverageCost ||
    (previousCurrentPrice !== undefined && pricesMatch(holding.avg_cost, previousCurrentPrice))

  if (currentPrice === undefined || !averageCostLooksAutoFilled) {
    return { ...holding, ticker }
  }

  return { ...holding, ticker, avg_cost: currentPrice }
}

export function Portfolio() {
  const { data, loading, error, refresh } = useDashboardData()
  const [viewMode, setViewMode] = useState<PortfolioViewMode>('summary')
  const [draftHoldings, setDraftHoldings] = useState<PortfolioHoldingInput[]>([])
  const [allowTruncateSave, setAllowTruncateSave] = useState(false)
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
      : { date: '', market_overview: [], tickers: [], portfolio_summary: null, portfolio_risk: null, pm_view: null }
  const portfolio = latestDay.portfolio_summary as PortfolioSummaryData | null | undefined
  const commandCenterData = useMemo(
    () =>
      buildPortfolioCommandCenter({
        portfolioSummary: portfolio,
        portfolioRisk: latestDay.portfolio_risk,
        pmEventExposure: latestDay.pm_view?.event_exposure_items ?? [],
        pmSwapCandidates: latestDay.pm_view?.swap_candidates ?? [],
        tickerAnalyses: latestDay.tickers,
      }),
    [latestDay.pm_view, latestDay.portfolio_risk, latestDay.tickers, portfolio],
  )
  const aggregatedDraft = useMemo(() => aggregateHoldings(draftHoldings), [draftHoldings])
  const quickSummaryGroups = useMemo(
    () => aggregatedDraft.filter((group) => group.ticker !== 'NEW'),
    [aggregatedDraft],
  )
  const tickerOptions = useMemo(
    () =>
      buildTickerOptions({
        analyses: latestDay.tickers,
        holdings: [...portfolioStatus.holdings, ...draftHoldings],
        positions: portfolio?.positions ?? [],
      }),
    [draftHoldings, latestDay.tickers, portfolio?.positions, portfolioStatus.holdings],
  )
  const currentPriceByTicker = useMemo(
    () =>
      buildCurrentPriceLookup({
        analyses: latestDay.tickers,
        positions: portfolio?.positions ?? [],
      }),
    [latestDay.tickers, portfolio?.positions],
  )
  const baselineHoldings = useMemo(() => portfolioStatus.holdings, [portfolioStatus.holdings])
  const changedLotCount = useMemo(
    () => countChangedLots(baselineHoldings, draftHoldings),
    [baselineHoldings, draftHoldings],
  )
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
  if (!data || data.days.length === 0) {
    return (
      <EmptyState
        title="표시할 포트폴리오 데이터가 없습니다."
        description="대시보드 출력 파일이 준비되면 보유 종목 요약과 편집기가 여기에 표시됩니다."
      />
    )
  }

  async function handleSave() {
    const validationError = validateDraftHoldings(draftHoldings)
    if (validationError) {
      pushToast('error', validationError)
      return
    }

    const saveOptions =
      allowTruncateSave && draftHoldings.length < baselineHoldings.length ? { allowTruncate: true } : undefined
    const result = saveOptions ? await saveHoldings(draftHoldings, saveOptions) : await saveHoldings(draftHoldings)
    if (!result.ok) {
      pushToast('error', result.message)
      return
    }

    pushToast('success', '포트폴리오를 저장했습니다. 리서치 실행은 대시보드 자동화에서 계속 수동으로 진행할 수 있습니다.')
    setAllowTruncateSave(false)
    setViewMode('summary')
  }

  function handleCancel() {
    setAllowTruncateSave(false)
    setDraftHoldings(prepareInitialDraft(portfolioStatus.holdings))
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
            aria-pressed={viewMode === 'summary'}
            onClick={() => setViewMode('summary')}
          >
            요약 보기
          </button>
          <button
            type="button"
            className={`preset-chip ${viewMode === 'edit' ? 'active' : ''}`}
            aria-pressed={viewMode === 'edit'}
            onClick={() => {
              setAllowTruncateSave(false)
              setDraftHoldings(prepareInitialDraft(portfolioStatus.holdings))
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
            <EmptyState
              title="포트폴리오 데이터가 없습니다."
              description="편집 모드에서 첫 lot를 추가한 뒤 저장하면 이후 요약과 손익 계산이 여기에 반영됩니다."
              className="dashboard-empty-state"
            />
          ) : (
            <>
              <PortfolioCommandCenter data={commandCenterData} asOf={latestDay.pm_view?.as_of ?? latestDay.date} />

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
              <p>각 lot를 한 화면에서 바로 수정하고 저장할 수 있습니다.</p>
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
            <QuickEditSummary
              groups={quickSummaryGroups}
              lotCount={draftHoldings.length}
              changedLotCount={changedLotCount}
            />

            <div className="portfolio-quick-edit-list" aria-label="포트폴리오 lot 빠른 편집">
              {draftHoldings.map((holding, index) => (
                <PortfolioLotEditor
                  key={`${holding.ticker || 'NEW'}-${index}`}
                  holding={holding}
                  rowIndex={index}
                  tickerOptions={tickerOptions}
                  currentPriceByTicker={currentPriceByTicker}
                  onChange={(nextHolding) =>
                    setDraftHoldings((current) =>
                      current.map((entry, entryIndex) => (entryIndex === index ? nextHolding : entry)),
                    )
                  }
                  onDelete={() => {
                    setAllowTruncateSave(true)
                    setDraftHoldings((current) => current.filter((_, entryIndex) => entryIndex !== index))
                  }}
                />
              ))}
            </div>
          </div>

          <button
          type="button"
          className="portfolio-add-lot-button standalone"
          aria-label="새 보유 lot 추가"
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
          <span className="u-price-delta" style={{ color: changeColor(dailyChange) }}>
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

function QuickEditSummary({
  groups,
  lotCount,
  changedLotCount,
}: {
  groups: AggregatedHolding[]
  lotCount: number
  changedLotCount: number
}) {
  return (
    <div className="portfolio-quick-summary">
      <div className="portfolio-quick-summary-stats" aria-label="편집 요약">
        <span>{lotCount} lot</span>
        <span>{groups.length} 종목</span>
        <span>{changedLotCount}개 변경</span>
      </div>
      {groups.length > 0 ? (
        <div className="portfolio-quick-summary-groups">
          {groups.map((group) => (
            <span key={group.ticker}>
              <strong>{group.ticker}</strong> {group.totalShares.toLocaleString()}주 / 평균{' '}
              {formatMoney(group.weightedAvgCost, group.currency)}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function PortfolioLotEditor({
  holding,
  rowIndex,
  tickerOptions,
  currentPriceByTicker,
  onChange,
  onDelete,
}: {
  holding: PortfolioHoldingInput
  rowIndex: number
  tickerOptions: string[]
  currentPriceByTicker: Map<string, number>
  onChange: (holding: PortfolioHoldingInput) => void
  onDelete: () => void
}) {
  const lotLabel = holding.ticker || `새 lot ${rowIndex + 1}`
  const [pickerOpen, setPickerOpen] = useState(false)
  const [tickerFilter, setTickerFilter] = useState('')
  const visibleTickerOptions = tickerOptions.filter((ticker) =>
    ticker.includes(tickerFilter.trim().toUpperCase()),
  )

  function handleSelectTicker(ticker: string) {
    onChange(withDefaultAverageCost(holding, ticker, currentPriceByTicker))
    setTickerFilter('')
    setPickerOpen(false)
  }

  return (
    <div className="portfolio-lot-editor">
      <div className="portfolio-ticker-picker">
        <span>티커</span>
        <button
          type="button"
          className="portfolio-ticker-picker-button"
          aria-label={`${lotLabel} ticker selector`}
          aria-haspopup="listbox"
          aria-expanded={pickerOpen}
          onClick={() => setPickerOpen((current) => !current)}
        >
          <strong>{holding.ticker || '티커 선택'}</strong>
          <small>{holding.ticker ? '선택됨' : '목록에서 선택'}</small>
        </button>
        {pickerOpen ? (
          <div className="portfolio-ticker-picker-menu">
            <input
              className="portfolio-ticker-search"
              type="search"
              value={tickerFilter}
              placeholder="목록 필터"
              aria-label="티커 목록 필터"
              onChange={(event) => setTickerFilter(event.target.value)}
            />
            <div className="portfolio-ticker-option-grid" role="listbox" aria-label="티커 선택 목록">
              {visibleTickerOptions.length > 0 ? (
                visibleTickerOptions.map((ticker) => (
                  <button
                    key={ticker}
                    type="button"
                    role="option"
                    aria-selected={holding.ticker === ticker}
                    className={`portfolio-ticker-option ${holding.ticker === ticker ? 'active' : ''}`}
                    onClick={() => handleSelectTicker(ticker)}
                  >
                    {ticker}
                  </button>
                ))
              ) : (
                <span className="portfolio-ticker-empty">선택 가능한 티커가 없습니다.</span>
              )}
            </div>
          </div>
        ) : null}
      </div>
      <label>
        <span>수량</span>
        <input
          aria-label={`${lotLabel} 수량`}
          type="number"
          min={0.0001}
          step={0.01}
          value={holding.shares}
          onChange={(event) => onChange({ ...holding, shares: Number(event.target.value) })}
        />
      </label>
      <label>
        <span>평균단가</span>
        <input
          aria-label={`${lotLabel} 평균단가`}
          type="number"
          min={0}
          step={0.01}
          value={holding.avg_cost}
          onChange={(event) => onChange({ ...holding, avg_cost: Number(event.target.value) })}
        />
      </label>
      <label>
        <span>통화</span>
        <select
          aria-label={`${lotLabel} 통화`}
          value={holding.currency}
          onChange={(event) => onChange({ ...holding, currency: event.target.value })}
        >
          <option value="USD">USD</option>
          <option value="KRW">KRW</option>
        </select>
      </label>
      <button type="button" className="portfolio-delete-lot-button" aria-label={`${lotLabel} lot 삭제`} onClick={onDelete}>
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
