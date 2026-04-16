import type { Dispatch, SetStateAction } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ErrorState } from '../components/ErrorState'
import { MacroContextBar } from '../components/MacroContextBar'
import { MarketOverview } from '../components/MarketOverview'
import { MarketRegimeBanner } from '../components/MarketRegimeBanner'
import { SectorSummary } from '../components/SectorSummary'
import { DashboardSkeleton } from '../components/Skeleton'
import {
  CatalystFeed,
  EarningsBoard,
  SignalPerformanceBoard,
  TodaySetupBoard,
} from '../components/TraderDashboardPanels'
import { WatchlistTable } from '../components/WatchlistTable'
import { useDashboardData } from '../hooks/useDashboardData'
import { useLocalResearchAutomation } from '../hooks/useLocalResearchAutomation'
import type { TickerAnalysisData, WeeklyReportSection } from '../types'
import {
  buildCatalystFeedSections,
  buildEarningsBoardSections,
  buildSetupCards,
  buildSignalPerformanceHighlights,
  computeSetupScore,
  computeTargetUpsidePercent,
  getLatestCatalystItem,
  getNextEarningsEvent,
} from '../utils/trader'

const SECTOR_LABELS: Record<string, string> = {
  Technology: '기술',
  Semiconductors: '반도체',
  Healthcare: '헬스케어',
  Financials: '금융',
  Energy: '에너지',
  'Consumer Discretionary': '경기소비재',
  'Consumer Staples': '필수소비재',
  Industrials: '산업재',
  'Communication Services': '커뮤니케이션',
  Utilities: '유틸리티',
  'Real Estate': '부동산',
  Materials: '소재',
}

type TraderFilters = {
  earningsWithin30d: boolean
  rvolHigh: boolean
  rsPositive: boolean
  hardCatalystOnly: boolean
  shortFloatHigh: boolean
  strongBuyUpside: boolean
}

type WatchlistSortMode = 'score' | 'earnings' | 'catalyst'
type DensityMode = 'compact' | 'comfortable' | 'focus'
type ToastTone = 'success' | 'error' | 'info'

type ToastItem = {
  id: number
  tone: ToastTone
  message: string
}

const PRESET_ACCOUNT_SIZES = [10000, 50000, 100000]

export function Dashboard() {
  const navigate = useNavigate()
  const { data, loading, refreshing, error, refresh } = useDashboardData()
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const tickerInputRef = useRef<HTMLInputElement | null>(null)
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSector, setSelectedSector] = useState('ALL')
  const [accountSize, setAccountSize] = useState(10000)
  const [watchlistSort, setWatchlistSort] = useState<WatchlistSortMode>('score')
  const [density, setDensity] = useState<DensityMode>('comfortable')

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    const sync = () => { setDensity(mq.matches ? 'compact' : 'comfortable') }
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [])

  const [tickerInput, setTickerInput] = useState('')
  const [autoRunAfterAdd, setAutoRunAfterAdd] = useState(false)
  const [pendingNavigationTicker, setPendingNavigationTicker] = useState<string | null>(null)
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const [traderFilters, setTraderFilters] = useState<TraderFilters>({
    earningsWithin30d: false,
    rvolHigh: false,
    rsPositive: false,
    hardCatalystOnly: false,
    shortFloatHigh: false,
    strongBuyUpside: false,
  })

  function pushToast(tone: ToastTone, message: string) {
    const id = Date.now() + Math.floor(Math.random() * 1000)
    setToasts((current) => [...current, { id, tone, message }])
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id))
    }, 3200)
  }

  const {
    status: automationStatus,
    available: automationAvailable,
    pendingAction,
    addTickerToWatchlist,
    runResearch,
  } = useLocalResearchAutomation({
    onRunCompleted: () => {
      refresh()
      setSelectedIdx(null)
      if (pendingNavigationTicker) {
        const targetTicker = pendingNavigationTicker
        setPendingNavigationTicker(null)
        pushToast('success', `${targetTicker} 리서치가 끝나서 상세페이지로 이동했습니다.`)
        navigate(`/ticker/${targetTicker}`)
      } else {
        pushToast('success', '리서치 실행이 완료되었습니다. 최신 결과를 불러왔습니다.')
      }
    },
  })

  const days = data?.days ?? []
  const rawIdx = selectedIdx ?? Math.max(days.length - 1, 0)
  const idx = days.length > 0 ? Math.min(rawIdx, days.length - 1) : 0
  const day = days[idx] ?? { date: '', market_overview: [], tickers: [] }
  const normalizedQuery = searchQuery.trim().toLowerCase()

  const sectors = useMemo(
    () =>
      Array.from(new Set(day.tickers.map((ticker) => ticker.data_snapshot['Sector'] || '기타'))).sort((a, b) =>
        a.localeCompare(b),
      ),
    [day.tickers],
  )

  const filteredTickers = useMemo(
    () =>
      day.tickers.filter((ticker) => {
        const matchesQuery =
          normalizedQuery.length === 0 ||
          ticker.ticker.toLowerCase().includes(normalizedQuery) ||
          ticker.name.toLowerCase().includes(normalizedQuery)

        const sector = ticker.data_snapshot['Sector'] || '기타'
        const matchesSector = selectedSector === 'ALL' || sector === selectedSector
        const matchesTraderFilters = applyTraderFilters(ticker, traderFilters)
        return matchesQuery && matchesSector && matchesTraderFilters
      }),
    [day.tickers, normalizedQuery, selectedSector, traderFilters],
  )

  const sortedWatchlistTickers = useMemo(
    () => sortWatchlistTickers(filteredTickers, watchlistSort),
    [filteredTickers, watchlistSort],
  )
  const topSetupCards = useMemo(() => buildSetupCards(filteredTickers, 5), [filteredTickers])
  const earningsBoardSections = useMemo(() => buildEarningsBoardSections(day.tickers), [day.tickers])
  const catalystFeedSections = useMemo(() => buildCatalystFeedSections(day.tickers), [day.tickers])
  const signalHighlights = useMemo(() => buildSignalPerformanceHighlights(data?.signal_stats), [data?.signal_stats])
  const emptyState = useMemo(
    () => buildEmptyStateMessage(searchQuery, selectedSector, traderFilters),
    [searchQuery, selectedSector, traderFilters],
  )

  useEffect(() => {
    document.title = '대시보드 · Stock Research'
  }, [])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      const tagName = target?.tagName ?? ''
      const isTyping =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        tagName === 'SELECT' ||
        target?.isContentEditable

      if (event.key === '/' && !isTyping) {
        event.preventDefault()
        searchInputRef.current?.focus()
        searchInputRef.current?.select()
        return
      }

      if (event.key === 'Escape') {
        if (document.activeElement instanceof HTMLElement) {
          document.activeElement.blur()
        }
        if (searchQuery) {
          setSearchQuery('')
        }
        if (tickerInput) {
          setTickerInput('')
        }
        return
      }

      if (event.key.toLowerCase() === 'r' && !event.metaKey && !event.ctrlKey && !event.altKey && !isTyping) {
        event.preventDefault()
        refresh()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [refresh, searchQuery, tickerInput])

  if (loading) return <DashboardSkeleton />
  if (error) return <ErrorState message={error} />
  if (!data || data.days.length === 0) return <p className="status">No data available.</p>

  async function handleAddTicker() {
    const normalizedTicker = normalizeTickerInput(tickerInput)
    if (!normalizedTicker) {
      pushToast('error', '티커 형식이 올바르지 않습니다. 영문 대문자, 숫자, 점(.) 또는 하이픈(-)만 사용할 수 있습니다.')
      return
    }

    const result = await addTickerToWatchlist(normalizedTicker)
    if (!result.ok) {
      pushToast('error', result.message)
      return
    }

    setTickerInput('')
    setSearchQuery(result.ticker)

    if (result.added) {
      setPendingNavigationTicker(result.ticker)
      if (autoRunAfterAdd) {
        pushToast('info', `${result.ticker}를 추가했습니다. 바로 리서치를 실행합니다.`)
        const runResult = await runResearch()
        if (!runResult.ok) {
          pushToast('error', runResult.message)
        }
      } else {
        pushToast('success', `${result.ticker}를 watchlist에 추가했습니다. 리서치를 실행하면 상세페이지로 이동합니다.`)
      }
      return
    }

    setPendingNavigationTicker(null)
    pushToast('info', `${result.ticker}는 이미 watchlist에 있어서 상세페이지로 바로 이동합니다.`)
    navigate(`/ticker/${result.ticker}`)
  }

  async function handleRunResearch() {
    const result = await runResearch()
    if (!result.ok) {
      pushToast('error', result.message)
      return
    }
    pushToast('info', '리서치를 시작했습니다. 완료되면 자동으로 새 결과를 불러옵니다.')
  }

  return (
    <div className="dashboard" data-density={density}>
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
        <h2>부자 되고 싶어요 · {day.date}</h2>
        {data.days.length > 1 && (
          <select className="date-select" value={idx} onChange={(e) => setSelectedIdx(Number(e.target.value))}>
            {data.days.map((entry, index) => (
              <option key={entry.date} value={index}>
                {entry.date}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="dashboard-quick-bar">
        <div className="dashboard-automation-panel">
          <div className="dashboard-automation-copy">
            <strong>로컬 리서치 자동화</strong>
            <p>티커를 watchlist에 추가하고 기존 배치 파이프라인을 바로 실행할 수 있습니다.</p>
          </div>

          {automationAvailable ? (
            <>
              <div className="dashboard-automation-controls">
                <input
                  ref={tickerInputRef}
                  className="dashboard-search dashboard-ticker-input"
                  type="text"
                  inputMode="text"
                  autoCapitalize="characters"
                  placeholder="예: TSLA"
                  value={tickerInput}
                  onChange={(event) => setTickerInput(event.target.value.toUpperCase())}
                  disabled={automationStatus.running || pendingAction === 'add'}
                />
                <button
                  type="button"
                  className="primary-action-button"
                  onClick={handleAddTicker}
                  disabled={!tickerInput.trim() || automationStatus.running || pendingAction === 'add'}
                >
                  {pendingAction === 'add' ? '추가 중...' : '티커 추가'}
                </button>
                <button
                  type="button"
                  className="secondary-action-button"
                  onClick={handleRunResearch}
                  disabled={automationStatus.running || pendingAction === 'run'}
                >
                  {automationStatus.running || pendingAction === 'run' ? '리서치 실행 중...' : '리서치 실행'}
                </button>
              </div>
              <label className="dashboard-automation-option">
                <input
                  type="checkbox"
                  checked={autoRunAfterAdd}
                  onChange={(event) => setAutoRunAfterAdd(event.target.checked)}
                  disabled={automationStatus.running || pendingAction === 'add' || pendingAction === 'run'}
                />
                <span>새 티커를 추가하면 바로 리서치를 실행합니다.</span>
              </label>
              <p className="dashboard-automation-hint">입력 형식: 영문 대문자 시작, 숫자/점/하이픈 허용. 예: TSLA, BRK-B, BF.B</p>
              <div className={`dashboard-automation-status stage-${automationStatus.stage}`}>
                <span className="dashboard-automation-stage">{automationStatus.stageLabel}</span>
                <p>{automationStatus.message}</p>
              </div>
            </>
          ) : (
            <div className="dashboard-automation-status stage-idle">
              <span className="dashboard-automation-stage">로컬 전용</span>
              <p>이 기능은 `npm run dev`로 띄운 로컬 개발 서버에서만 사용할 수 있습니다.</p>
            </div>
          )}
        </div>

        <div className="dashboard-controls">
          <input
            ref={searchInputRef}
            className="dashboard-search"
            type="search"
            placeholder="티커 또는 종목명 검색"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <select className="dashboard-filter" value={selectedSector} onChange={(e) => setSelectedSector(e.target.value)}>
            <option value="ALL">전체 섹터</option>
            {sectors.map((sector) => (
              <option key={sector} value={sector}>
                {SECTOR_LABELS[sector] ?? sector}
              </option>
            ))}
          </select>
          <label className="account-size-control">
            <span>계좌 크기</span>
            <input
              type="number"
              min={1000}
              step={1000}
              value={accountSize}
              onChange={(e) => setAccountSize(Number(e.target.value) || 10000)}
            />
          </label>
        </div>

        <div className="dashboard-quick-bar-row">
          <div className="preset-chip-row compact-row">
            {PRESET_ACCOUNT_SIZES.map((preset) => (
              <button
                key={preset}
                type="button"
                className={`preset-chip ${accountSize === preset ? 'active' : ''}`}
                onClick={() => setAccountSize(preset)}
              >
                {preset.toLocaleString()} USD
              </button>
            ))}
          </div>

          <div className="watchlist-sort-row compact-row">
            <span className="watchlist-sort-label">카드 정렬</span>
            <button
              type="button"
              className={`preset-chip ${watchlistSort === 'score' ? 'active' : ''}`}
              onClick={() => setWatchlistSort('score')}
            >
              점수순
            </button>
            <button
              type="button"
              className={`preset-chip ${watchlistSort === 'earnings' ? 'active' : ''}`}
              onClick={() => setWatchlistSort('earnings')}
            >
              실적 임박순
            </button>
            <button
              type="button"
              className={`preset-chip ${watchlistSort === 'catalyst' ? 'active' : ''}`}
              onClick={() => setWatchlistSort('catalyst')}
            >
              하드 촉매순
            </button>
          </div>
        </div>

        <div className="dashboard-quick-bar-row">
          <div className="trader-filter-row compact-row">
            <FilterChip
              label="실적 30일 이내"
              active={traderFilters.earningsWithin30d}
              onClick={() => toggleTraderFilter(setTraderFilters, 'earningsWithin30d')}
            />
            <FilterChip
              label="RVOL > 1.2"
              active={traderFilters.rvolHigh}
              onClick={() => toggleTraderFilter(setTraderFilters, 'rvolHigh')}
            />
            <FilterChip
              label="RS > 0"
              active={traderFilters.rsPositive}
              onClick={() => toggleTraderFilter(setTraderFilters, 'rsPositive')}
            />
            <FilterChip
              label="Hard catalyst only"
              active={traderFilters.hardCatalystOnly}
              onClick={() => toggleTraderFilter(setTraderFilters, 'hardCatalystOnly')}
            />
            <FilterChip
              label="공매도 > 5%"
              active={traderFilters.shortFloatHigh}
              onClick={() => toggleTraderFilter(setTraderFilters, 'shortFloatHigh')}
            />
            <FilterChip
              label="Strong Buy + 목표가 15%+"
              active={traderFilters.strongBuyUpside}
              onClick={() => toggleTraderFilter(setTraderFilters, 'strongBuyUpside')}
            />
          </div>

          <div className="density-chip-row compact-row">
            <span className="watchlist-sort-label">밀도</span>
            <button type="button" className={`preset-chip ${density === 'compact' ? 'active' : ''}`} onClick={() => setDensity('compact')}>
              Compact
            </button>
            <button
              type="button"
              className={`preset-chip ${density === 'comfortable' ? 'active' : ''}`}
              onClick={() => setDensity('comfortable')}
            >
              Comfortable
            </button>
            <button type="button" className={`preset-chip ${density === 'focus' ? 'active' : ''}`} onClick={() => setDensity('focus')}>
              Focus
            </button>
          </div>
        </div>
      </div>

      {refreshing && <p className="dashboard-refresh-note">최신 output을 다시 불러오는 중입니다.</p>}

      <TodaySetupBoard cards={topSetupCards} />
      <EarningsBoard sections={earningsBoardSections} />

      <div className="dashboard-split-grid">
        <CatalystFeed sections={catalystFeedSections} />
        <SignalPerformanceBoard highlights={signalHighlights} />
      </div>

      <MarketRegimeBanner regime={day.market_regime} />
      <MacroContextBar macroContext={day.macro_context} />
      {(data.weekly_summary?.weekly_report || data.weekly_summary?.weekly_insight) ? (
        <section className="ticker-detail-section-shell">
          <h3>주간 인사이트</h3>
          <div className="detail-note-card">
            {data.weekly_summary?.weekly_report ? (
              <div className="weekly-report-panel">
                {data.weekly_summary.weekly_report.headline ? (
                  <strong className="weekly-report-headline">{data.weekly_summary.weekly_report.headline}</strong>
                ) : null}
                {data.weekly_summary.weekly_report.summary ? (
                  <p className="weekly-report-summary">{data.weekly_summary.weekly_report.summary}</p>
                ) : data.weekly_summary.weekly_insight ? (
                  <p className="weekly-report-summary">{data.weekly_summary.weekly_insight}</p>
                ) : null}
                <div className="weekly-report-grid">
                  <WeeklyReportCard index={1} title="시장 환경 요약" section={data.weekly_summary.weekly_report.market_environment} />
                  <WeeklyReportCard index={2} title="핵심 이동 종목 Top 3" section={data.weekly_summary.weekly_report.top_movers} />
                  <WeeklyReportCard index={3} title="시그널 성과 리뷰" section={data.weekly_summary.weekly_report.signal_review} />
                  <WeeklyReportCard index={4} title="리스크 포인트" section={data.weekly_summary.weekly_report.risk_points} />
                  <WeeklyReportCard index={5} title="다음 주 액션 플랜" section={data.weekly_summary.weekly_report.next_week_action_plan} />
                  <WeeklyReportCard index={6} title="포트폴리오 제안" section={data.weekly_summary.weekly_report.portfolio_suggestions} />
                </div>
              </div>
            ) : (
              <p>{data.weekly_summary?.weekly_insight}</p>
            )}
            <div className="watchlist-chip-row">
              <span className="period-badge">
                {data.weekly_summary?.iso_year}-W{String(data.weekly_summary?.iso_week).padStart(2, '0')}
              </span>
              <span className="period-badge">
                {data.weekly_summary?.start_date} ~ {data.weekly_summary?.end_date}
              </span>
            </div>
          </div>
        </section>
      ) : null}
      <MarketOverview entries={day.market_overview} />
      <SectorSummary tickers={day.tickers} />

      {sortedWatchlistTickers.length > 0 ? (
        <WatchlistTable tickers={sortedWatchlistTickers} accountSize={accountSize} density={density} />
      ) : (
        <div className="dashboard-empty-state">
          <strong>{emptyState.title}</strong>
          <p>{emptyState.body}</p>
        </div>
      )}
    </div>
  )
}

function normalizeTickerInput(value: string): string {
  const normalized = value.trim().toUpperCase()
  return /^[A-Z][A-Z0-9.-]{0,14}$/.test(normalized) ? normalized : ''
}

function WeeklyReportCard({
  index,
  title,
  section,
}: {
  index: number
  title: string
  section?: WeeklyReportSection
}) {
  const normalizedItems = normalizeWeeklyReportItems(section)
  return (
    <article className="weekly-report-card">
      <span className="weekly-report-card-kicker">{index}. {title}</span>
      <p className="weekly-report-card-summary">{section?.summary ?? '데이터가 아직 충분하지 않습니다.'}</p>
      {normalizedItems.length > 0 ? (
        <ul className="weekly-report-card-list">
          {normalizedItems.map((item, idx) => (
            <li key={`${title}-${idx}`}>{item}</li>
          ))}
        </ul>
      ) : null}
    </article>
  )
}

function normalizeWeeklyReportItems(section?: WeeklyReportSection): string[] {
  if (!section) return []
  const details = Array.isArray(section.details) ? section.details.filter(Boolean) : []
  const items = Array.isArray(section.items) ? section.items : []
  const normalizedItems = items
    .map((item) => {
      if (typeof item === 'string') return item
      if (!item || typeof item !== 'object') return ''
      const parts = [
        item.ticker ? `${item.ticker}${item.name ? ` (${item.name})` : ''}` : item.name ?? '',
        item.weekly_change,
        item.catalyst,
        item.decision_change,
      ].filter(Boolean)
      return parts.join(' · ')
    })
    .filter(Boolean)
  return [...details, ...normalizedItems]
}

function applyTraderFilters(ticker: TickerAnalysisData, filters: TraderFilters): boolean {
  if (filters.earningsWithin30d) {
    const earnings = getNextEarningsEvent(ticker)
    const daysUntil = earnings ? parseInt(earnings.days_until, 10) : Number.NaN
    if (Number.isNaN(daysUntil) || daysUntil > 30) {
      return false
    }
  }

  if (filters.rvolHigh) {
    const rvol = parseNumericValue(ticker.price_action?.relative_volume)
    if (rvol === null || rvol < 1.2) {
      return false
    }
  }

  if (filters.rsPositive) {
    const rs = parseNumericValue(ticker.price_action?.rs_vs_spy)
    if (rs === null || rs <= 0) {
      return false
    }
  }

  if (filters.hardCatalystOnly) {
    if (getLatestCatalystItem(ticker)?.level !== 'hard') {
      return false
    }
  }

  if (filters.shortFloatHigh) {
    const shortFloat = parseNumericValue(ticker.fundamentals?.short_float_pct)
    if (shortFloat === null || shortFloat <= 5) {
      return false
    }
  }

  if (filters.strongBuyUpside) {
    const recommendation = (ticker.fundamentals?.analyst_recommendation ?? '').toLowerCase()
    const upside = computeTargetUpsidePercent(ticker)
    if (recommendation !== 'strong buy' || upside === null || upside < 15) {
      return false
    }
  }

  return true
}

function toggleTraderFilter(
  setTraderFilters: Dispatch<SetStateAction<TraderFilters>>,
  key: keyof TraderFilters,
) {
  setTraderFilters((current) => ({ ...current, [key]: !current[key] }))
}

function parseNumericValue(value?: string): number | null {
  if (!value) return null
  const match = value.replace(/,/g, '').match(/[-+]?\d*\.?\d+/)
  if (!match) return null
  const parsed = Number.parseFloat(match[0])
  return Number.isNaN(parsed) ? null : parsed
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button type="button" className={`preset-chip ${active ? 'active' : ''}`} onClick={onClick}>
      {label}
    </button>
  )
}

function sortWatchlistTickers(tickers: TickerAnalysisData[], mode: WatchlistSortMode): TickerAnalysisData[] {
  return [...tickers].sort((left, right) => {
    if (mode === 'earnings') {
      const leftDays = parseEventDays(getNextEarningsEvent(left)?.days_until)
      const rightDays = parseEventDays(getNextEarningsEvent(right)?.days_until)
      if (leftDays !== rightDays) {
        return leftDays - rightDays
      }
    }

    if (mode === 'catalyst') {
      const leftCatalyst = getLatestCatalystItem(left)
      const rightCatalyst = getLatestCatalystItem(right)
      const leftRank = catalystLevelRank(leftCatalyst?.level)
      const rightRank = catalystLevelRank(rightCatalyst?.level)
      if (leftRank !== rightRank) {
        return rightRank - leftRank
      }
      const sortScoreDiff = (rightCatalyst?.sortScore ?? 0) - (leftCatalyst?.sortScore ?? 0)
      if (sortScoreDiff !== 0) {
        return sortScoreDiff
      }
    }

    const scoreDiff = computeSetupScore(right).score - computeSetupScore(left).score
    if (scoreDiff !== 0) {
      return scoreDiff
    }

    return left.ticker.localeCompare(right.ticker)
  })
}

function parseEventDays(value?: string): number {
  if (!value) return Number.POSITIVE_INFINITY
  const parsed = Number.parseInt(value, 10)
  return Number.isNaN(parsed) ? Number.POSITIVE_INFINITY : parsed
}

function catalystLevelRank(level?: string): number {
  if (level === 'hard') return 3
  if (level === 'medium') return 2
  if (level === 'soft') return 1
  return 0
}

function buildEmptyStateMessage(query: string, sector: string, filters: TraderFilters): { title: string; body: string } {
  const hasFilter = Object.values(filters).some(Boolean)
  if (query.trim()) {
    return {
      title: '검색 결과가 없습니다.',
      body: `"${query.trim()}"와 일치하는 종목이 없습니다. 티커 영문자로 다시 찾거나 검색어를 조금 줄여보세요.`,
    }
  }

  if (sector !== 'ALL' && hasFilter) {
    return {
      title: '조건이 너무 좁습니다.',
      body: '선택한 섹터와 현재 필터 조합을 동시에 만족하는 종목이 없습니다. 섹터 또는 필터 하나를 먼저 풀어보세요.',
    }
  }

  if (filters.hardCatalystOnly) {
    return {
      title: '오늘은 하드 촉매만으로 남은 종목이 없습니다.',
      body: '현재 조건에서는 hard catalyst가 비어 있습니다. 실적 임박순으로 바꾸거나 Catalyst Feed에서 medium 단계까지 넓혀보세요.',
    }
  }

  if (hasFilter) {
    return {
      title: '현재 필터에 맞는 종목이 없습니다.',
      body: '필터 조합이 너무 타이트합니다. 필터를 한두 개 줄이거나 카드 정렬을 바꿔 다음 후보를 확인해보세요.',
    }
  }

  return {
    title: '표시할 종목이 없습니다.',
    body: '아직 오늘 결과가 생성되지 않았거나 output이 비어 있습니다. 로컬 리서치를 실행한 뒤 다시 확인해보세요.',
  }
}
