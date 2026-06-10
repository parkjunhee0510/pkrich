import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  useSectorsData,
  type SectorsBenchmark,
  type SectorsTicker,
} from '../hooks/useSectorsData'
import { Sparkline } from '../components/Sparkline'
import { FiftyTwoWeekBadge } from '../components/FiftyTwoWeekBadge'
import { SectorBenchmarkHeader } from '../components/SectorBenchmark'
import { relativeReturn } from '../utils/sectorBenchmark'
import { CorrelationHeatmap } from '../components/CorrelationHeatmap'
import { DashboardSkeleton } from '../components/Skeleton'
import { ErrorState } from '../components/ErrorState'

export function SectorDetail() {
  const { sectorId } = useParams<{ sectorId: string }>()
  const { data, loading, error } = useSectorsData()

  useEffect(() => {
    const name = data?.sectors.find((s) => s.id === sectorId)?.name
    document.title = name ? `${name} · Stock Research` : '섹터 · Stock Research'
  }, [data, sectorId])

  if (loading) return <DashboardSkeleton />
  if (error) return <ErrorState message={error} />
  if (!data) return <p className="empty">데이터 없음</p>

  const sector = data.sectors.find((s) => s.id === sectorId)
  if (!sector) {
    return (
      <section className="sector-detail-page">
        <p className="empty">
          <Link to="/sectors">← 섹터 목록으로</Link>
          <br />섹터 <code>{sectorId}</code>를 찾을 수 없습니다.
        </p>
      </section>
    )
  }

  return (
    <section className="sector-detail-page">
      <header className="page-header">
        <Link to="/sectors" className="back-link">← 섹터 목록</Link>
        <h1>{sector.name}</h1>
        {sector.description && <p className="page-subtitle">{sector.description}</p>}
        <p className="page-meta">업데이트: {data.updated_at}</p>
      </header>

      {sector.benchmark && <SectorBenchmarkHeader benchmark={sector.benchmark} />}

      <CorrelationHeatmap tickers={sector.tickers} />

      <div className="sector-ticker-grid">
        {sector.tickers.map((ticker) => (
          <SectorTickerCard
            key={ticker.ticker}
            ticker={ticker}
            benchmark={sector.benchmark}
          />
        ))}
      </div>
    </section>
  )
}

function SectorTickerCard({
  ticker,
  benchmark,
}: {
  ticker: SectorsTicker
  benchmark?: SectorsBenchmark
}) {
  const reuseFromWatchlist = ticker.error === 'reuse_from_watchlist'
  const closes = ticker.history.map((p) => p.close)
  const changeClass = ticker.change_percent.startsWith('-') ? 'negative' : 'positive'

  const rel1m = benchmark && benchmark.history.length >= 2
    ? relativeReturn(ticker.history, benchmark.history, 21)
    : null

  return (
    <article className="sector-ticker-card">
      <header className="sector-ticker-head">
        <div>
          <h3>
            <Link to={`/ticker/${ticker.ticker}`}>{ticker.ticker}</Link>
          </h3>
          <p className="sector-ticker-name">{ticker.name}</p>
        </div>
        <div className="sector-ticker-price">
          {ticker.price && <div className="price">{ticker.price}</div>}
          {ticker.change_percent && (
            <div className={`change ${changeClass}`}>{ticker.change_percent}</div>
          )}
        </div>
      </header>

      {reuseFromWatchlist ? (
        <p className="sector-ticker-note">
          워치리스트에 포함된 종목입니다. 상세한 가격/뉴스는{' '}
          <Link to={`/ticker/${ticker.ticker}`}>티커 상세 페이지</Link>에서 확인하세요.
        </p>
      ) : (
        <>
          {closes.length >= 2 ? (
            <>
              <div className="sector-ticker-chart">
                <Sparkline values={closes} width={280} height={60} />
              </div>
              <FiftyTwoWeekBadge history={ticker.history} />
              {rel1m && benchmark && (
                <div
                  className={`sector-relative ${rel1m.relative >= 0 ? 'positive' : 'negative'}`}
                  title={`티커 1M: ${rel1m.ticker.toFixed(2)}% · ${benchmark.ticker} 1M: ${rel1m.benchmark.toFixed(2)}%`}
                >
                  vs {benchmark.ticker} (1M):{' '}
                  <strong>
                    {rel1m.relative >= 0 ? '+' : ''}
                    {rel1m.relative.toFixed(2)}%
                  </strong>
                </div>
              )}
            </>
          ) : (
            <p className="sector-ticker-note">가격 데이터 없음</p>
          )}

          {ticker.news.length > 0 ? (
            <ul className="sector-ticker-news">
              {ticker.news.map((n, idx) => (
                <li key={`${n.link}-${idx}`}>
                  {n.link ? (
                    <a href={n.link} target="_blank" rel="noopener noreferrer">
                      {n.title}
                    </a>
                  ) : (
                    <span>{n.title}</span>
                  )}
                  <span className="news-meta">
                    {n.source && ` · ${n.source}`}
                    {n.published_at && ` (${n.published_at})`}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="sector-ticker-note muted">관련 뉴스 없음</p>
          )}
        </>
      )}
    </article>
  )
}
