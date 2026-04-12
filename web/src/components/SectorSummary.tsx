import { Link } from 'react-router-dom'
import type { TickerAnalysisData } from '../types'
import { parseNumericChange, changeColor } from '../utils/format'

interface SectorRow {
  sector: string
  sectorKo: string
  tickerCount: number
  avgChange: number
  topGainer: { ticker: string; change: number } | null
  topLoser: { ticker: string; change: number } | null
}

const SECTOR_KO: Record<string, string> = {
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

function buildSectorRows(tickers: TickerAnalysisData[]): SectorRow[] {
  const sectorMap = new Map<string, { changes: number[]; tickers: { ticker: string; change: number }[] }>()

  for (const t of tickers) {
    const sector = t.data_snapshot['Sector'] || 'Other'
    const change = parseNumericChange(t.data_snapshot['Daily Change'] ?? '0')

    const existing = sectorMap.get(sector) ?? { changes: [], tickers: [] }
    sectorMap.set(sector, {
      changes: [...existing.changes, change],
      tickers: [...existing.tickers, { ticker: t.ticker, change }],
    })
  }

  const rows: SectorRow[] = []
  for (const [sector, data] of sectorMap) {
    const avgChange = data.changes.reduce((sum, c) => sum + c, 0) / data.changes.length
    const sorted = [...data.tickers].sort((a, b) => b.change - a.change)
    rows.push({
      sector,
      sectorKo: SECTOR_KO[sector] ?? sector,
      tickerCount: data.tickers.length,
      avgChange,
      topGainer: sorted.length > 0 && sorted[0].change > 0 ? sorted[0] : null,
      topLoser: sorted.length > 0 && sorted[sorted.length - 1].change < 0 ? sorted[sorted.length - 1] : null,
    })
  }

  return rows.sort((a, b) => b.avgChange - a.avgChange)
}

export function SectorSummary({ tickers }: { tickers: TickerAnalysisData[] }) {
  const rows = buildSectorRows(tickers)

  if (rows.length === 0) return null

  return (
    <section className="sector-summary">
      <h3>섹터 퍼포먼스</h3>
      <div className="sector-summary-grid">
        {rows.map((row) => (
          <div key={row.sector} className="sector-card">
            <div className="sector-card-header">
              <span className="sector-card-name">{row.sectorKo}</span>
              <span className="sector-card-count">{row.tickerCount}종목</span>
            </div>
            <div className="sector-card-change" style={{ color: changeColor(row.avgChange) }}>
              {row.avgChange >= 0 ? '+' : ''}{row.avgChange.toFixed(2)}%
            </div>
            <div className="sector-card-extremes">
              {row.topGainer && (
                <span className="sector-gainer">
                  <Link to={`/ticker/${row.topGainer.ticker}`}>{row.topGainer.ticker}</Link>{' '}
                  <span style={{ color: 'var(--color-up)' }}>{row.topGainer.change >= 0 ? '+' : ''}{row.topGainer.change.toFixed(1)}%</span>
                </span>
              )}
              {row.topLoser && (
                <span className="sector-loser">
                  <Link to={`/ticker/${row.topLoser.ticker}`}>{row.topLoser.ticker}</Link>{' '}
                  <span style={{ color: 'var(--color-down)' }}>{row.topLoser.change.toFixed(1)}%</span>
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
