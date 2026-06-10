import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useSectorsData } from '../hooks/useSectorsData'
import { DashboardSkeleton } from '../components/Skeleton'
import { ErrorState } from '../components/ErrorState'
import { SectorPerformanceBars } from '../components/SectorPerformanceBars'
import { countFiftyTwoStrength } from '../utils/fiftyTwoWeek'

export function Sectors() {
  const { data, loading, error } = useSectorsData()

  useEffect(() => {
    document.title = '섹터 탐색 · Stock Research'
  }, [])

  if (loading) return <DashboardSkeleton />
  if (error) return <ErrorState message={`섹터 데이터를 불러오지 못했습니다: ${error}`} />
  if (!data || data.sectors.length === 0) {
    return <p className="empty">등록된 섹터가 없습니다. <code>config/sectors.yaml</code>을 확인하세요.</p>
  }

  return (
    <section className="sectors-page">
      <header className="page-header">
        <h1>섹터 탐색</h1>
        <p className="page-subtitle">
          LLM을 돌리지 않는 읽기 전용 뷰 — 가격 차트와 관련 뉴스만 보여줍니다. 종목은{' '}
          <code>config/sectors.yaml</code>에서 추가/삭제할 수 있습니다.
        </p>
        <p className="page-meta">업데이트: {data.updated_at}</p>
      </header>

      <SectorPerformanceBars sectors={data.sectors} />

      <div className="sector-grid">
        {data.sectors.map((sector) => {
          const strength = countFiftyTwoStrength(sector.tickers.map((t) => t.history))
          return (
            <Link key={sector.id} to={`/sectors/${sector.id}`} className="sector-card">
              <h2>{sector.name}</h2>
              {sector.description && <p className="sector-description">{sector.description}</p>}
              {strength.total > 0 && (
                <div className="sector-strength" title="52주 레인지 상단 75% 이상 / 하단 25% 이하 종목 수">
                  <span className="sector-strength-chip strong">52W ↑ {strength.strong}</span>
                  <span className="sector-strength-chip weak">52W ↓ {strength.weak}</span>
                  <span className="sector-strength-chip muted">
                    {strength.total} 커버
                  </span>
                </div>
              )}
              <div className="sector-ticker-chips">
                {sector.tickers.slice(0, 8).map((t) => (
                  <span key={t.ticker} className="ticker-chip">
                    {t.ticker}
                  </span>
                ))}
                {sector.tickers.length > 8 && (
                  <span className="ticker-chip muted">+{sector.tickers.length - 8}</span>
                )}
              </div>
            </Link>
          )
        })}
      </div>
    </section>
  )
}
