import type { Dispatch, SetStateAction } from 'react'
import { useEffect, useMemo, useState } from 'react'
import { ErrorState } from '../components/ErrorState'
import { MarketOverview } from '../components/MarketOverview'
import { SectorSummary } from '../components/SectorSummary'
import { DashboardSkeleton } from '../components/Skeleton'
import { CatalystFeed, EarningsBoard, SignalPerformanceBoard, TodaySetupBoard } from '../components/TraderDashboardPanels'
import { WatchlistTable } from '../components/WatchlistTable'
import { useDashboardData } from '../hooks/useDashboardData'
import { useLocalResearchAutomation } from '../hooks/useLocalResearchAutomation'
import type { TickerAnalysisData } from '../types'
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

const PRESET_ACCOUNT_SIZES = [10000, 50000, 100000]

export function Dashboard() {
  const { data, loading, refreshing, error, refresh } = useDashboardData()
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSector, setSelectedSector] = useState('ALL')
  const [accountSize, setAccountSize] = useState(10000)
  const [watchlistSort, setWatchlistSort] = useState<WatchlistSortMode>('score')
  const [density, setDensity] = useState<DensityMode>('comfortable')
  const [tickerInput, setTickerInput] = useState('')
  const [traderFilters, setTraderFilters] = useState<TraderFilters>({
    earningsWithin30d: false,
    rvolHigh: false,
    rsPositive: false,
    hardCatalystOnly: false,
    shortFloatHigh: false,
    strongBuyUpside: false,
  })

  const { status: automationStatus, available: automationAvailable, pendingAction, addTickerToWatchlist, runResearch } =
    useLocalResearchAutomation({
      onRunCompleted: () => {
        refresh()
        setSelectedIdx(null)
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

  if (loading) return <DashboardSkeleton />
  if (error) return <ErrorState message={error} />
  if (!data || data.days.length === 0) return <p className="status">No data available.</p>

  async function handleAddTicker() {
    const result = await addTickerToWatchlist(tickerInput)
    if (result.ok) {
      setTickerInput('')
      setSearchQuery(result.ticker)
    }
  }

  async function handleRunResearch() {
    await runResearch()
  }

  return (
    <div className="dashboard" data-density={density}>
      <div className="dashboard-header">
        <h2>트레이더 워크스페이스 · {day.date}</h2>
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
            <button type="button" className={`preset-chip ${density === 'comfortable' ? 'active' : ''}`} onClick={() => setDensity('comfortable')}>
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
    if (rvol === null || rvol <= 1.2) {
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
