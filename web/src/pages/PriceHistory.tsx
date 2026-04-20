import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ErrorState } from '../components/ErrorState'
import { TablePageSkeleton } from '../components/Skeleton'
import { useDashboardData } from '../hooks/useDashboardData'
import { usePriceHistoryLive } from '../hooks/usePriceHistoryLive'
import type { PriceHistoryRow, TickerAnalysisData } from '../types'
import { changeColor, parseNumericChange, parsePrice } from '../utils/format'

const PriceChart = lazy(() =>
  import('../components/PriceChart').then((module) => ({ default: module.PriceChart })),
)

type PeriodFilter = '1W' | '1M' | '3M' | '6M' | 'ALL'
type TableSortKey = 'date' | 'open' | 'high' | 'low' | 'close' | 'volume' | 'change'
type SortDirection = 'asc' | 'desc'

const PERIODS: PeriodFilter[] = ['1W', '1M', '3M', '6M', 'ALL']

function subtractDays(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split('-').map((value) => parseInt(value, 10))
  const utc = new Date(Date.UTC(year, month - 1, day))
  utc.setUTCDate(utc.getUTCDate() - days)
  return utc.toISOString().slice(0, 10)
}

function getPeriodCutoff(latestDate: string | undefined, period: PeriodFilter): string | null {
  if (!latestDate || period === 'ALL') return null
  switch (period) {
    case '1W':
      return subtractDays(latestDate, 7)
    case '1M':
      return subtractDays(latestDate, 30)
    case '3M':
      return subtractDays(latestDate, 90)
    case '6M':
      return subtractDays(latestDate, 180)
    default:
      return null
  }
}

function parseTableNumber(value?: string): number {
  return parsePrice(value ?? '')
}

function getLatestTickerRow(rows: PriceHistoryRow[]): PriceHistoryRow | null {
  if (rows.length === 0) return null
  return [...rows].sort((left, right) => right.date.localeCompare(left.date))[0] ?? null
}

function buildTickerNameMap(tickers: TickerAnalysisData[] | undefined): Record<string, string> {
  return (tickers ?? []).reduce<Record<string, string>>((acc, ticker) => {
    acc[ticker.ticker] = ticker.name
    return acc
  }, {})
}

export function PriceHistory() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [searchTerm, setSearchTerm] = useState('')
  const [period, setPeriod] = useState<PeriodFilter>('3M')
  const [sortKey, setSortKey] = useState<TableSortKey>('date')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const { data: dashboardData, loading: dashboardLoading, error: dashboardError } = useDashboardData()
  const { allRows, tickers, loading: priceLoading, lastUpdated, refresh } = usePriceHistoryLive()

  useEffect(() => {
    document.title = '시세 · Stock Research'
  }, [])

  const latestDay = dashboardData?.days[dashboardData.days.length - 1]
  const tickerNameMap = useMemo(() => buildTickerNameMap(latestDay?.tickers), [latestDay?.tickers])
  const currentTickerParam = searchParams.get('ticker')?.toUpperCase() ?? ''
  const filteredTickers = useMemo(() => {
    const normalized = searchTerm.trim().toLowerCase()
    return tickers.filter((item) => {
      if (!normalized) return true
      const name = tickerNameMap[item.ticker] ?? ''
      return item.ticker.toLowerCase().includes(normalized) || name.toLowerCase().includes(normalized)
    })
  }, [searchTerm, tickerNameMap, tickers])

  const selectedTicker = useMemo(() => {
    const available = tickers.map((item) => item.ticker)
    if (currentTickerParam && available.includes(currentTickerParam)) {
      return currentTickerParam
    }
    return filteredTickers[0]?.ticker ?? tickers[0]?.ticker ?? ''
  }, [currentTickerParam, filteredTickers, tickers])

  useEffect(() => {
    if (selectedTicker && currentTickerParam !== selectedTicker) {
      setSearchParams({ ticker: selectedTicker }, { replace: true })
    }
  }, [currentTickerParam, selectedTicker, setSearchParams])

  const selectedRows = useMemo(
    () => allRows.filter((row) => row.ticker === selectedTicker),
    [allRows, selectedTicker],
  )
  const latestRow = useMemo(() => getLatestTickerRow(selectedRows), [selectedRows])
  const selectedAnalysis = useMemo(
    () => latestDay?.tickers.find((ticker) => ticker.ticker === selectedTicker) ?? null,
    [latestDay?.tickers, selectedTicker],
  )
  const cutoff = getPeriodCutoff(latestRow?.date, period)
  const periodRows = useMemo(
    () => selectedRows.filter((row) => !cutoff || row.date >= cutoff),
    [cutoff, selectedRows],
  )
  const sortedRows = useMemo(() => {
    const rows = [...periodRows]
    rows.sort((left, right) => {
      let result = 0
      if (sortKey === 'date') {
        result = left.date.localeCompare(right.date)
      } else if (sortKey === 'change') {
        result = parseNumericChange(left.daily_change ?? '0') - parseNumericChange(right.daily_change ?? '0')
      } else {
        result = parseTableNumber(left[sortKey]) - parseTableNumber(right[sortKey])
      }
      return sortDirection === 'asc' ? result : -result
    })
    return rows
  }, [periodRows, sortDirection, sortKey])

  if (dashboardLoading || priceLoading) return <TablePageSkeleton title="시세" />
  if (dashboardError) return <ErrorState message={dashboardError} />

  const selectedSummary = tickers.find((item) => item.ticker === selectedTicker)
  const stats = [
    { label: '현재가', value: latestRow?.price ?? selectedSummary?.latestPrice ?? 'N/A' },
    { label: '일변동', value: latestRow?.daily_change ?? selectedSummary?.latestChange ?? 'N/A' },
    { label: '52주 고가', value: latestRow?.['52w_high'] || selectedAnalysis?.data_snapshot['52W High'] || 'N/A' },
    { label: '52주 저가', value: latestRow?.['52w_low'] || selectedAnalysis?.data_snapshot['52W Low'] || 'N/A' },
    { label: '거래량', value: latestRow?.volume || selectedAnalysis?.data_snapshot.Volume || 'N/A' },
    { label: 'PER', value: latestRow?.trailing_pe || selectedAnalysis?.data_snapshot['Trailing P/E'] || 'N/A' },
    { label: '시가총액', value: latestRow?.market_cap || selectedAnalysis?.data_snapshot['Market Cap'] || 'N/A' },
  ]

  const handleSort = (nextKey: TableSortKey) => {
    if (sortKey === nextKey) {
      setSortDirection((current) => (current === 'desc' ? 'asc' : 'desc'))
      return
    }
    setSortKey(nextKey)
    setSortDirection('desc')
  }

  const updatedLabel = lastUpdated ? new Date(lastUpdated).toLocaleString('ko-KR') : 'N/A'

  return (
    <div className="price-history-page">
      <div className="dashboard-header">
        <div>
          <h2>시세</h2>
          <p className="section-kicker">전체 종목의 과거 시세 기록과 최신 상태를 한눈에 확인합니다.</p>
        </div>
        <div className="price-history-toolbar-meta">
          <span className="price-history-updated">마지막 갱신 {updatedLabel}</span>
          <span className="price-history-live-indicator">자동 갱신 30초</span>
          <button type="button" className="secondary-action-button" onClick={() => void refresh()}>
            새로고침
          </button>
        </div>
      </div>

      <section className="price-history-section">
        <input
          className="dashboard-search"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="종목명 또는 티커 검색"
        />
        <div className="price-history-chip-row">
          {filteredTickers.map((item) => {
            const change = parseNumericChange(item.latestChange)
            return (
              <button
                key={item.ticker}
                type="button"
                className={`price-history-chip${item.ticker === selectedTicker ? ' active' : ''}`}
                onClick={() => setSearchParams({ ticker: item.ticker })}
              >
                <strong>{item.ticker}</strong>
                <span>{tickerNameMap[item.ticker] ?? item.ticker}</span>
                <em>{item.latestPrice}</em>
                <em style={{ color: changeColor(change) }}>{item.latestChange}</em>
              </button>
            )
          })}
        </div>
      </section>

      <section className="price-history-section">
        <div className="preset-chip-row">
          {PERIODS.map((value) => (
            <button
              key={value}
              type="button"
              className={`preset-chip ${period === value ? 'active' : ''}`}
              onClick={() => setPeriod(value)}
            >
              {value}
            </button>
          ))}
        </div>
      </section>

      <section className="price-history-section">
        <div className="price-history-stats-grid">
          {stats.map((stat) => (
            <div key={stat.label} className="signal-summary-card">
              <div className="signal-summary-direction">{stat.label}</div>
              <div className="signal-summary-count">{stat.value}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="price-history-section">
        {periodRows.length > 0 ? (
          <Suspense fallback={<div className="status">차트를 불러오는 중...</div>}>
            <PriceChart rows={periodRows} height={480} />
          </Suspense>
        ) : (
          <p className="empty">선택한 종목의 시세 데이터가 없습니다.</p>
        )}
      </section>

      <section className="price-history-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>시세 기록</h3>
            <p className="section-kicker">{selectedTicker} · 최신 우선, 컬럼 정렬 지원</p>
          </div>
        </div>
        <div className="watchlist-table-shell price-history-table-shell">
          <table className="watchlist-table price-history-table">
            <thead>
              <tr>
                <SortableHead label="날짜" active={sortKey === 'date'} direction={sortDirection} onClick={() => handleSort('date')} />
                <SortableHead label="시가" active={sortKey === 'open'} direction={sortDirection} onClick={() => handleSort('open')} />
                <SortableHead label="고가" active={sortKey === 'high'} direction={sortDirection} onClick={() => handleSort('high')} />
                <SortableHead label="저가" active={sortKey === 'low'} direction={sortDirection} onClick={() => handleSort('low')} />
                <SortableHead label="종가" active={sortKey === 'close'} direction={sortDirection} onClick={() => handleSort('close')} />
                <SortableHead label="거래량" active={sortKey === 'volume'} direction={sortDirection} onClick={() => handleSort('volume')} />
                <SortableHead label="변동" active={sortKey === 'change'} direction={sortDirection} onClick={() => handleSort('change')} />
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row) => {
                const change = parseNumericChange(row.daily_change ?? '0')
                return (
                  <tr key={`${row.ticker}-${row.date}`}>
                    <td>{row.date}</td>
                    <td>{row.open || 'N/A'}</td>
                    <td>{row.high || 'N/A'}</td>
                    <td>{row.low || 'N/A'}</td>
                    <td>{row.close || row.price || 'N/A'}</td>
                    <td>{row.volume || 'N/A'}</td>
                    <td style={{ color: changeColor(change) }}>{row.daily_change || 'N/A'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function SortableHead({
  label,
  active,
  direction,
  onClick,
}: {
  label: string
  active: boolean
  direction: SortDirection
  onClick: () => void
}) {
  return (
    <th>
      <button type="button" className={`price-history-sort${active ? ' active' : ''}`} onClick={onClick}>
        <span>{label}</span>
        <span>{active ? (direction === 'desc' ? '↓' : '↑') : '↕'}</span>
      </button>
    </th>
  )
}
