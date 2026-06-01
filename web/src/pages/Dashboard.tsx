import type { Dispatch, ReactNode, SetStateAction } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ActionChangeFeed } from '../components/ActionChangeFeed'
import { DashboardNewsDesk } from '../components/DashboardNewsDesk'
import { ErrorState } from '../components/ErrorState'
import { MacroContextBar } from '../components/MacroContextBar'
import { MacroNarrativePanel } from '../components/MacroNarrativePanel'
import { MarketOverview } from '../components/MarketOverview'
import { MarketMoodSectorBriefing } from '../components/MarketMoodSectorBriefing'
import { RiskIntelPanel } from '../components/RiskIntelPanel'
import { DashboardSkeleton } from '../components/Skeleton'
import { TodayPriorityQueue } from '../components/TodayPriorityQueue'
import {
  CatalystFeed,
  EarningsBoard,
  SignalPerformanceBoard,
  TodaySetupBoard,
} from '../components/TraderDashboardPanels'
import { WatchlistTable } from '../components/WatchlistTable'
import { TodayDecisionStrip } from '../components/TodayDecisionStrip'
import { useDashboardData } from '../hooks/useDashboardData'
import { EmptyState } from '../components/ui/EmptyState'
import { useQualityReliabilityLoopData } from '../hooks/useQualityReliabilityLoopData'
import { useRiskIntelData } from '../hooks/useRiskIntelData'
import { useSearchEvidenceData } from '../hooks/useSearchEvidenceData'
import type { DailyEntry, TickerAnalysisData, WeeklyReportSection } from '../types'
import { buildActionChangeFeed, findPreviousValidDay } from '../utils/actionChangeFeed'
import { buildTodayDecisionStrip } from '../utils/todayDecisionStrip'
import { buildTodayPriorityQueue } from '../utils/todayPriorityQueue'
import { buildDashboardNewsDeskViewModel } from '../utils/newsDesk'
import { buildMarketMoodSummary, deriveSectorMoodInsights } from '../utils/sectorMood'
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
const EMPTY_DAYS: DailyEntry[] = []
const EMPTY_DAY: DailyEntry = { date: '', market_overview: [], tickers: [] }

export function Dashboard() {
  const { data, loading, refreshing, error, refresh } = useDashboardData({ pollIntervalMs: 60000 })
  const { summary: riskIntelSummary, graph: riskIntelGraph } = useRiskIntelData()
  const { searchEvidence } = useSearchEvidenceData()
  const { qualityLoop } = useQualityReliabilityLoopData()
  const searchInputRef = useRef<HTMLInputElement | null>(null)
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

  const [traderFilters, setTraderFilters] = useState<TraderFilters>({
    earningsWithin30d: false,
    rvolHigh: false,
    rsPositive: false,
    hardCatalystOnly: false,
    shortFloatHigh: false,
    strongBuyUpside: false,
  })

  const days = data?.days ?? EMPTY_DAYS
  const rawIdx = selectedIdx ?? Math.max(days.length - 1, 0)
  const idx = days.length > 0 ? Math.min(rawIdx, days.length - 1) : 0
  const day = days[idx] ?? EMPTY_DAY
  const previousDay = useMemo(() => findPreviousValidDay(days, idx), [days, idx])
  const actionChangeFeed = useMemo(
    () => buildActionChangeFeed(day, previousDay),
    [day, previousDay],
  )
  const todayDecisionStrip = useMemo(
    () => buildTodayDecisionStrip(day, previousDay, { feed: actionChangeFeed }),
    [day, previousDay, actionChangeFeed],
  )
  const todayPriorityQueue = useMemo(
    () =>
      buildTodayPriorityQueue({
        day,
        previousDay,
        searchEvidence,
        riskIntelSummary,
        qualityLoop,
        limit: 8,
      }),
    [day, previousDay, searchEvidence, riskIntelSummary, qualityLoop],
  )
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
  const activeTraderFilterCount = useMemo(
    () => Object.values(traderFilters).filter(Boolean).length,
    [traderFilters],
  )
  const topSetupCards = useMemo(() => buildSetupCards(filteredTickers, 3), [filteredTickers])
  const earningsBoardSections = useMemo(() => buildEarningsBoardSections(day.tickers), [day.tickers])
  const catalystFeedSections = useMemo(() => buildCatalystFeedSections(day.tickers), [day.tickers])
  const signalHighlights = useMemo(() => buildSignalPerformanceHighlights(data?.signal_stats), [data?.signal_stats])
  const sectorMood = useMemo(
    () =>
      deriveSectorMoodInsights({
        tickers: day.tickers,
        marketRegime: day.market_regime,
        macroContext: day.macro_context,
      }),
    [day.tickers, day.market_regime, day.macro_context],
  )
  const newsDeskViewModel = useMemo(
    () =>
      buildDashboardNewsDeskViewModel({
        day,
        previousDay,
        sectorMood,
        actionChangeFeed,
        todayDecisionStrip,
        todayPriorityQueue,
        riskIntelSummary,
        searchEvidence,
        qualityLoop,
        dataError: error,
        limit: 6,
      }),
    [
      day,
      previousDay,
      sectorMood,
      actionChangeFeed,
      todayDecisionStrip,
      todayPriorityQueue,
      riskIntelSummary,
      searchEvidence,
      qualityLoop,
      error,
    ],
  )
  const decisionCounts = useMemo(() => countDecisions(day.tickers), [day.tickers])
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
        return
      }

      if (event.key.toLowerCase() === 'r' && !event.metaKey && !event.ctrlKey && !event.altKey && !isTyping) {
        event.preventDefault()
        refresh()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [refresh, searchQuery])

  if (loading && !data) return <DashboardSkeleton />
  if (error && !data) return <ErrorState message={error} />
  if (!data || data.days.length === 0) {
    return (
      <EmptyState
        title="표시할 대시보드 데이터가 없습니다."
        description="출력 파일이 생성되면 워치리스트와 리서치 요약이 여기에 표시됩니다."
      />
    )
  }

  return (
    <div className="dashboard" data-density={density}>
      <div className="dashboard-header">
        <div className="dashboard-header-main">
          <h2>부자 되고 싶어요 · {day.date}</h2>
          <div className="dashboard-header-meta">
            <span className="dashboard-stat-chip">전체 {day.tickers.length}개</span>
            <span className="dashboard-stat-chip">표시 {sortedWatchlistTickers.length}개</span>
            <span className="dashboard-stat-chip">매수 {decisionCounts.buy}개</span>
            <span className="dashboard-stat-chip">관찰 {decisionCounts.watch}개</span>
            <span className="dashboard-stat-chip">회피 {decisionCounts.avoid}개</span>
            <span className="dashboard-stat-chip">
              섹터: {selectedSector === 'ALL' ? '전체' : (SECTOR_LABELS[selectedSector] ?? selectedSector)}
            </span>
            <span className="dashboard-stat-chip">필터 {activeTraderFilterCount}개 적용</span>
            <span className="dashboard-stat-chip">
              검색: {searchQuery.trim() ? `"${searchQuery.trim()}"` : '없음'}
            </span>
          </div>
        </div>
        {data.days.length > 1 && (
          <select
            className="date-select"
            value={idx}
            aria-label="대시보드 날짜 선택"
            onChange={(e) => setSelectedIdx(Number(e.target.value))}
          >
            {data.days.map((entry, index) => (
              <option key={entry.date} value={index}>
                {entry.date}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="dashboard-quick-bar">
        <div className="dashboard-controls">
          <input
            ref={searchInputRef}
            className="dashboard-search"
            type="search"
            placeholder="티커 또는 종목명 검색"
            aria-label="티커 또는 종목명 검색"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <select
            className="dashboard-filter"
            value={selectedSector}
            aria-label="섹터 필터"
            onChange={(e) => setSelectedSector(e.target.value)}
          >
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
              aria-label="계좌 크기"
              value={accountSize}
              onChange={(e) => setAccountSize(Number(e.target.value) || 10000)}
            />
          </label>
        </div>
        <p className="dashboard-filter-summary">
          현재 보기: {sortedWatchlistTickers.length} / {day.tickers.length}
          {selectedSector !== 'ALL' ? ` · ${SECTOR_LABELS[selectedSector] ?? selectedSector}` : ''}
          {activeTraderFilterCount > 0 ? ` · 추가 조건 ${activeTraderFilterCount}개` : ''}
        </p>

        <div className="dashboard-quick-bar-row">
          <div className="preset-chip-row compact-row">
            {PRESET_ACCOUNT_SIZES.map((preset) => (
              <button
                key={preset}
                type="button"
                className={`preset-chip ${accountSize === preset ? 'active' : ''}`}
                aria-pressed={accountSize === preset}
                aria-label={`계좌 크기를 ${preset.toLocaleString()} USD로 설정`}
                onClick={() => setAccountSize(preset)}
              >
                {preset.toLocaleString()} USD
              </button>
            ))}
          </div>

          <div className="watchlist-sort-row compact-row">
            <span className="watchlist-sort-label">정렬 방식</span>
            <button
              type="button"
              className={`preset-chip ${watchlistSort === 'score' ? 'active' : ''}`}
              aria-pressed={watchlistSort === 'score'}
              onClick={() => setWatchlistSort('score')}
            >
              점수순
            </button>
            <button
              type="button"
              className={`preset-chip ${watchlistSort === 'earnings' ? 'active' : ''}`}
              aria-pressed={watchlistSort === 'earnings'}
              onClick={() => setWatchlistSort('earnings')}
            >
              실적 임박순
            </button>
            <button
              type="button"
              className={`preset-chip ${watchlistSort === 'catalyst' ? 'active' : ''}`}
              aria-pressed={watchlistSort === 'catalyst'}
              onClick={() => setWatchlistSort('catalyst')}
            >
              강한 재료순
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
              label="강한 재료만"
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
            <button
              type="button"
              className={`preset-chip ${density === 'compact' ? 'active' : ''}`}
              aria-pressed={density === 'compact'}
              onClick={() => setDensity('compact')}
            >
              간결
            </button>
            <button
              type="button"
              className={`preset-chip ${density === 'comfortable' ? 'active' : ''}`}
              aria-pressed={density === 'comfortable'}
              onClick={() => setDensity('comfortable')}
            >
              기본
            </button>
            <button
              type="button"
              className={`preset-chip ${density === 'focus' ? 'active' : ''}`}
              aria-pressed={density === 'focus'}
              onClick={() => setDensity('focus')}
            >
              집중
            </button>
          </div>
        </div>
      </div>

      {refreshing && <p className="dashboard-refresh-note">최신 output을 다시 불러오는 중입니다.</p>}

      <DashboardNewsDesk viewModel={newsDeskViewModel} refreshing={refreshing} />

      <TodayPriorityQueue queue={todayPriorityQueue} />

      <TodayDecisionStrip strip={todayDecisionStrip} />

      <ActionChangeFeed feed={actionChangeFeed} />

      {riskIntelSummary && riskIntelSummary.cards.length > 0 ? (
        <RiskIntelPanel summary={riskIntelSummary} graph={riskIntelGraph} compact />
      ) : null}

      <TodaySetupBoard cards={topSetupCards} />

      <DashboardAccordionSection
        title="실적 일정 · 재료 · 판단 신호"
        summary={`실적 일정 ${earningsBoardSections.reduce((sum, section) => sum + section.items.length, 0)}건 · 재료 ${Object.values(catalystFeedSections).reduce((sum, items) => sum + items.length, 0)}건`}
      >
        <EarningsBoard sections={earningsBoardSections} />
        <div className="dashboard-split-grid">
          <CatalystFeed sections={catalystFeedSections} />
          <SignalPerformanceBoard highlights={signalHighlights} />
        </div>
      </DashboardAccordionSection>

      <DashboardAccordionSection
        title="오늘 시장 분위기"
        summary={buildMarketMoodSummary(day.market_regime, sectorMood)}
        defaultOpen
      >
        <MarketMoodSectorBriefing
          marketRegime={day.market_regime}
          macroContext={day.macro_context}
          sectorMood={sectorMood}
        />
        <MacroNarrativePanel narrative={day.macro_context?.macro_narrative} regime={day.market_regime} />
        <MacroContextBar macroContext={day.macro_context} />
        <MarketOverview entries={day.market_overview} />
      </DashboardAccordionSection>

      {(data.weekly_summary?.weekly_report || data.weekly_summary?.weekly_insight) ? (
        <DashboardAccordionSection
          title="주간 인사이트"
          summary={data.weekly_summary?.weekly_report?.headline ?? data.weekly_summary?.weekly_report?.summary ?? data.weekly_summary?.weekly_insight ?? '주간 보고서'}
          defaultOpen
        >
          <section className="ticker-detail-section-shell">
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
                    <WeeklyReportCard index={3} title="판단 신호 성과 리뷰" section={data.weekly_summary.weekly_report.signal_review} />
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
        </DashboardAccordionSection>
      ) : null}

      {sortedWatchlistTickers.length > 0 ? (
        <WatchlistTable tickers={sortedWatchlistTickers} accountSize={accountSize} density={density} />
      ) : (
        <EmptyState title={emptyState.title} description={emptyState.body} className="dashboard-empty-state" />
      )}
    </div>
  )
}

function DashboardAccordionSection({
  title,
  summary,
  children,
  defaultOpen = false,
}: {
  title: string
  summary: string
  children: ReactNode
  defaultOpen?: boolean
}) {
  return (
    <details className="dashboard-accordion-section" open={defaultOpen}>
      <summary>
        <div className="dashboard-accordion-copy">
          <div className="dashboard-accordion-text">
            <strong>{title}</strong>
            <span>{summary}</span>
          </div>
          <span className="dashboard-accordion-arrow" aria-hidden="true">▾</span>
        </div>
      </summary>
      <div className="dashboard-accordion-body">{children}</div>
    </details>
  )
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

function countDecisions(tickers: TickerAnalysisData[]): { buy: number; watch: number; avoid: number } {
  return tickers.reduce(
    (counts, ticker) => {
      const action = ticker.decision?.action
      if (action === 'buy') counts.buy += 1
      else if (action === 'avoid') counts.avoid += 1
      else counts.watch += 1
      return counts
    },
    { buy: 0, watch: 0, avoid: 0 },
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
    <button type="button" className={`preset-chip ${active ? 'active' : ''}`} aria-pressed={active} onClick={onClick}>
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

    const rightScore = typeof right.decision?.conviction === 'number' ? right.decision.conviction : computeSetupScore(right).score
    const leftScore = typeof left.decision?.conviction === 'number' ? left.decision.conviction : computeSetupScore(left).score
    const scoreDiff = rightScore - leftScore
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
      title: '오늘은 강한 재료만으로 남은 종목이 없습니다.',
      body: '현재 조건에서는 강한 재료가 잡히지 않았습니다. 실적 임박순으로 바꾸거나 재료 목록에서 범위를 조금 넓혀보세요.',
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
