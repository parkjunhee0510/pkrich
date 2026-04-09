import type { Dispatch, SetStateAction } from 'react'
import { useMemo, useState } from 'react'
import type { TickerAnalysisData } from '../types'
import { useDashboardData } from '../hooks/useDashboardData'
import { MarketOverview } from '../components/MarketOverview'
import { SectorSummary } from '../components/SectorSummary'
import { WatchlistTable } from '../components/WatchlistTable'
import { CatalystFeed, EarningsBoard, SignalPerformanceBoard, TodaySetupBoard } from '../components/TraderDashboardPanels'
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
  'Communication Services': '커뮤니케이션 서비스',
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

const PRESET_ACCOUNT_SIZES = [10000, 50000, 100000]

export function Dashboard() {
  const { data, loading, error } = useDashboardData()
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSector, setSelectedSector] = useState('ALL')
  const [accountSize, setAccountSize] = useState(10000)
  const [traderFilters, setTraderFilters] = useState<TraderFilters>({
    earningsWithin30d: false,
    rvolHigh: false,
    rsPositive: false,
    hardCatalystOnly: false,
    shortFloatHigh: false,
    strongBuyUpside: false,
  })

  if (loading) return <p className="status">Loading...</p>
  if (error) return <p className="status error">Failed to load data: {error}</p>
  if (!data || data.days.length === 0) return <p className="status">No data available.</p>

  const idx = selectedIdx ?? data.days.length - 1
  const day = data.days[idx]
  const sectors = Array.from(new Set(day.tickers.map((ticker) => ticker.data_snapshot['Sector'] || '기타'))).sort((a, b) => a.localeCompare(b))
  const normalizedQuery = searchQuery.trim().toLowerCase()

  const filteredTickers = day.tickers
    .filter((ticker) => {
      const matchesQuery =
        normalizedQuery.length === 0 ||
        ticker.ticker.toLowerCase().includes(normalizedQuery) ||
        ticker.name.toLowerCase().includes(normalizedQuery)

      const sector = ticker.data_snapshot['Sector'] || '기타'
      const matchesSector = selectedSector === 'ALL' || sector === selectedSector
      const matchesTraderFilters = applyTraderFilters(ticker, traderFilters)
      return matchesQuery && matchesSector && matchesTraderFilters
    })
    .sort((left, right) => computeSetupScore(right).score - computeSetupScore(left).score || left.ticker.localeCompare(right.ticker))

  const topSetupCards = useMemo(() => buildSetupCards(filteredTickers, 5), [filteredTickers])
  const earningsBoardSections = useMemo(() => buildEarningsBoardSections(day.tickers), [day.tickers])
  const catalystFeedSections = useMemo(() => buildCatalystFeedSections(day.tickers), [day.tickers])
  const signalHighlights = useMemo(() => buildSignalPerformanceHighlights(data.signal_stats), [data.signal_stats])

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>트레이더 워크스페이스 · {day.date}</h2>
        {data.days.length > 1 && (
          <select className="date-select" value={idx} onChange={(e) => setSelectedIdx(Number(e.target.value))}>
            {data.days.map((entry, index) => (
              <option key={entry.date} value={index}>{entry.date}</option>
            ))}
          </select>
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

      <div className="preset-chip-row">
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

      <div className="trader-filter-row">
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

      <TodaySetupBoard cards={topSetupCards} />
      <EarningsBoard sections={earningsBoardSections} />

      <div className="dashboard-split-grid">
        <CatalystFeed sections={catalystFeedSections} />
        <SignalPerformanceBoard highlights={signalHighlights} />
      </div>

      <MarketOverview entries={day.market_overview} />
      <SectorSummary tickers={day.tickers} />

      {filteredTickers.length > 0 ? (
        <WatchlistTable tickers={filteredTickers} accountSize={accountSize} />
      ) : (
        <p className="status">조건에 맞는 종목이 없습니다.</p>
      )}
    </div>
  )
}

function applyTraderFilters(ticker: TickerAnalysisData, filters: TraderFilters): boolean {
  if (filters.earningsWithin30d) {
    const earnings = getNextEarningsEvent(ticker)
    const daysUntil = earnings ? parseInt(earnings.days_until, 10) : NaN
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
