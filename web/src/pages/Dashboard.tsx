import { useState } from 'react'
import { useDashboardData } from '../hooks/useDashboardData'
import { MarketOverview } from '../components/MarketOverview'
import { WatchlistTable } from '../components/WatchlistTable'

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

export function Dashboard() {
  const { data, loading, error } = useDashboardData()
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSector, setSelectedSector] = useState('ALL')

  if (loading) return <p className="status">Loading...</p>
  if (error) return <p className="status error">Failed to load data: {error}</p>
  if (!data || data.days.length === 0) return <p className="status">No data available.</p>

  const idx = selectedIdx ?? data.days.length - 1
  const day = data.days[idx]
  const sectors = Array.from(new Set(day.tickers.map((ticker) => ticker.data_snapshot['Sector'] || '기타'))).sort((a, b) => a.localeCompare(b))
  const normalizedQuery = searchQuery.trim().toLowerCase()
  const filteredTickers = day.tickers.filter((ticker) => {
    const matchesQuery =
      normalizedQuery.length === 0 ||
      ticker.ticker.toLowerCase().includes(normalizedQuery) ||
      ticker.name.toLowerCase().includes(normalizedQuery)

    const sector = ticker.data_snapshot['Sector'] || '기타'
    const matchesSector = selectedSector === 'ALL' || sector === selectedSector
    return matchesQuery && matchesSector
  })

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>일일 리서치 · {day.date}</h2>
        {data.days.length > 1 && (
          <select className="date-select" value={idx} onChange={(e) => setSelectedIdx(Number(e.target.value))}>
            {data.days.map((d, i) => (
              <option key={d.date} value={i}>{d.date}</option>
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
      </div>

      <MarketOverview entries={day.market_overview} />
      {filteredTickers.length > 0 ? (
        <WatchlistTable tickers={filteredTickers} />
      ) : (
        <p className="status">조건에 맞는 종목이 없습니다.</p>
      )}
    </div>
  )
}
