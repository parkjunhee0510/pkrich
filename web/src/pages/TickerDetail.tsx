import { Suspense, lazy, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useDashboardData } from '../hooks/useDashboardData'
import { usePriceHistory } from '../hooks/usePriceHistory'
import { useTickerTimeline } from '../hooks/useTickerTimeline'
import { DataSnapshot } from '../components/DataSnapshot'
import { NewsItem } from '../components/NewsItem'
import { SecFilingBadges } from '../components/SecFilingBadges'
import { SignalBadge } from '../components/SignalBadge'
import { parseNumericChange, changeColor } from '../utils/format'

const FILING_TABS = ['실적', '배당', '주주총회', '기타 공시'] as const
type FilingTab = (typeof FILING_TABS)[number]
type FilingSort = 'latest' | 'oldest'
type FilingImpactLevel = '높음' | '보통' | '낮음'

const PriceChart = lazy(() =>
  import('../components/PriceChart').then((module) => ({ default: module.PriceChart })),
)

export function TickerDetail() {
  const { ticker } = useParams<{ ticker: string }>()
  const { data, loading, error } = useDashboardData()
  const { rows: priceRows, loading: priceLoading } = usePriceHistory(ticker)
  const { entries: timelineEntries, loading: timelineLoading } = useTickerTimeline(ticker)
  const [timelineWindow, setTimelineWindow] = useState<'30' | '90'>('30')
  const [selectedFilingTab, setSelectedFilingTab] = useState<FilingTab>('실적')
  const [filingSort, setFilingSort] = useState<FilingSort>('latest')
  const [filingQuery, setFilingQuery] = useState('')
  const [selectedFormType, setSelectedFormType] = useState('ALL')

  const latestDay = data?.days[data.days.length - 1]
  const analysis = latestDay?.tickers.find((t) => t.ticker === ticker)
  const pct = parseNumericChange(analysis?.data_snapshot['Daily Change'] ?? '0')
  const visibleTimeline = useMemo(() => {
    const limit = timelineWindow === '30' ? 30 : 90
    return timelineEntries.slice(0, limit)
  }, [timelineEntries, timelineWindow])
  const upcomingEvents = analysis?.upcoming_events ?? []
  const newsReferences = analysis?.news_references ?? []
  const keyNews = analysis?.key_news ?? []
  const secFilings = analysis?.sec_filings ?? []
  const financialHighlights = analysis?.financial_highlights ?? []
  const riskItems = analysis?.risks_or_watchpoints ?? []
  const quarterlyFinancials = analysis?.quarterly_financials ?? []
  const latestSecFiling = secFilings[0]
  const latestFilingImpactLevel = latestSecFiling
    ? estimateFilingImpactLevel(latestSecFiling.tag, latestSecFiling.form_type, latestSecFiling.title)
    : null
  const filingCounts = useMemo(
    () =>
      FILING_TABS.reduce<Record<FilingTab, number>>((acc, tag) => {
        acc[tag] = secFilings.filter((filing) => filing.tag === tag).length
        return acc
      }, { 실적: 0, 배당: 0, 주주총회: 0, '기타 공시': 0 }),
    [secFilings],
  )
  const availableFilingTabs = FILING_TABS.filter((tag) => filingCounts[tag] > 0)
  const activeFilingTab = availableFilingTabs.includes(selectedFilingTab)
    ? selectedFilingTab
    : availableFilingTabs[0] ?? '실적'
  const activeTabFilings = useMemo(
    () => secFilings.filter((filing) => filing.tag === activeFilingTab),
    [activeFilingTab, secFilings],
  )
  const availableFormTypes = useMemo(
    () =>
      Array.from(
        new Set(
          activeTabFilings
            .map((filing) => filing.form_type.trim())
            .filter((formType) => formType.length > 0),
        ),
      ).sort((a, b) => a.localeCompare(b)),
    [activeTabFilings],
  )
  const activeFormType = selectedFormType === 'ALL' || availableFormTypes.includes(selectedFormType)
    ? selectedFormType
    : 'ALL'
  const visibleSecFilings = useMemo(
    () =>
      activeTabFilings
        .filter((filing) => activeFormType === 'ALL' || filing.form_type === activeFormType)
        .filter((filing) => {
          const normalizedQuery = filingQuery.trim().toLowerCase()
          if (!normalizedQuery) {
            return true
          }
          return filing.title.toLowerCase().includes(normalizedQuery) || filing.form_type.toLowerCase().includes(normalizedQuery)
        })
        .sort((left, right) => compareFilingsByDate(left.published_at, right.published_at, filingSort)),
    [activeFormType, activeTabFilings, filingQuery, filingSort],
  )

  if (loading) return <p className="status">Loading...</p>
  if (error) return <p className="status error">Failed to load data: {error}</p>
  if (!data || !ticker) return <p className="status">No data available.</p>

  if (!analysis) {
    return <p className="status">Ticker {ticker} not found.</p>
  }

  return (
    <div className="ticker-detail">
      <Link to="/" className="back-link">&larr; Dashboard</Link>

      <div className="ticker-header">
        <div>
          <h2>{analysis.ticker} · {analysis.name}</h2>
          <span className="ticker-date">{analysis.date}</span>
          <div className="ticker-meta-row">
            <span className={`tone-badge tone-${analysis.news_tone?.label ?? 'neutral'}`}>
              Tone: {analysis.news_tone?.label ?? 'neutral'}
            </span>
            <span className="period-badge">7D {analysis.period_changes?.['7d'] ?? 'N/A'}</span>
            <span className="period-badge">30D {analysis.period_changes?.['30d'] ?? 'N/A'}</span>
          </div>
          <SecFilingBadges tags={analysis.sec_filing_tags ?? []} />
        </div>
        <div className="ticker-price-group">
          <span className="ticker-price">{analysis.data_snapshot['Price']}</span>
          <span style={{ color: changeColor(pct), fontWeight: 600, fontSize: '1.1rem' }}>
            {analysis.data_snapshot['Daily Change']}
          </span>
          <SignalBadge changePercent={pct} />
        </div>
      </div>

      {latestSecFiling && (
        <section className="latest-filing-card">
          <div className="latest-filing-head">
            <div>
              <h3>최신 공시</h3>
              <SecFilingBadges tags={latestSecFiling.tag ? [latestSecFiling.tag] : []} />
              {latestFilingImpactLevel && (
                <span className={`filing-impact-badge impact-${toImpactClassName(latestFilingImpactLevel)}`}>
                  예상 영향도 {latestFilingImpactLevel}
                </span>
              )}
            </div>
            <span className="news-meta">
              {latestSecFiling.source && `${latestSecFiling.source} · `}
              {latestSecFiling.published_at}
            </span>
          </div>
          <p className="latest-filing-title">{latestSecFiling.title}</p>
          <p className="latest-filing-summary">
            {buildFilingImpactSummary(latestSecFiling.tag, latestSecFiling.title)}
          </p>
          {latestSecFiling.link && (
            <a href={latestSecFiling.link} target="_blank" rel="noopener noreferrer">
              공시 원문 보기
            </a>
          )}
        </section>
      )}

      <section>
        <h3>Price History</h3>
        {priceLoading ? (
          <p>Loading chart...</p>
        ) : (
          <Suspense fallback={<p>Loading chart...</p>}>
            <PriceChart rows={priceRows} />
          </Suspense>
        )}
      </section>

      <section>
        <h3>요약</h3>
        <p>{analysis.summary}</p>
      </section>

      <section>
        <h3>다가오는 일정</h3>
        {upcomingEvents.length > 0 ? (
          <div className="event-badges">
            {upcomingEvents.map((event) => (
              <span key={`${event.type}-${event.date}`} className="event-badge">
                {event.label} {event.date} (D-{event.days_until})
              </span>
            ))}
          </div>
        ) : (
          <p className="empty">예정된 일정이 없습니다.</p>
        )}
      </section>

      <section>
        <h3>주요 뉴스</h3>
        {newsReferences.length > 0 ? (
          <ul className="news-list">
            {newsReferences.map((ref, i) => (
              <NewsItem key={i} item={ref} summary={keyNews[i]} />
            ))}
          </ul>
        ) : (
          <p className="empty">수집된 뉴스가 없습니다.</p>
        )}
      </section>

      <section>
        <h3>공시자료</h3>
        {secFilings.length > 0 ? (
          <>
            <div className="filing-toolbar">
              <div className="filing-tabs" role="tablist" aria-label="SEC filings">
                {availableFilingTabs.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    role="tab"
                    aria-selected={activeFilingTab === tag}
                    className={`filing-tab ${activeFilingTab === tag ? 'active' : ''}`}
                    onClick={() => setSelectedFilingTab(tag)}
                  >
                    {tag}
                    <span className="filing-tab-count">{filingCounts[tag]}</span>
                  </button>
                ))}
              </div>
              <div className="filing-controls">
                <input
                  type="search"
                  className="filing-search"
                  placeholder="공시 제목 또는 폼 검색"
                  value={filingQuery}
                  onChange={(event) => setFilingQuery(event.target.value)}
                />
                <select
                  className="filing-form-filter"
                  value={activeFormType}
                  onChange={(event) => setSelectedFormType(event.target.value)}
                >
                  <option value="ALL">전체 폼</option>
                  {availableFormTypes.map((formType) => (
                    <option key={formType} value={formType}>
                      {formType}
                    </option>
                  ))}
                </select>
                <div className="filing-sort-toggle" role="group" aria-label="filing sort">
                  <button
                    type="button"
                    className={filingSort === 'latest' ? 'active' : ''}
                    onClick={() => setFilingSort('latest')}
                  >
                    최신순
                  </button>
                  <button
                    type="button"
                    className={filingSort === 'oldest' ? 'active' : ''}
                    onClick={() => setFilingSort('oldest')}
                  >
                    날짜순
                  </button>
                </div>
              </div>
            </div>
            {visibleSecFilings.length > 0 ? (
              <ul className="news-list">
                {visibleSecFilings.map((filing, index) => (
                  <li key={`${filing.published_at}-${filing.title}-${index}`} className="news-item">
                    <SecFilingBadges tags={filing.tag ? [filing.tag] : []} />
                    {filing.form_type && <span className="filing-form-chip">{filing.form_type}</span>}
                    {filing.link ? (
                      <a href={filing.link} target="_blank" rel="noopener noreferrer">
                        {filing.title}
                      </a>
                    ) : (
                      <span>{filing.title}</span>
                    )}
                    <span className="news-meta">
                      {filing.source && ` · ${filing.source}`}
                      {filing.published_at && ` (${filing.published_at})`}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty">조건에 맞는 공시자료가 없습니다.</p>
            )}
          </>
        ) : (
          <p className="empty">표시할 공시자료가 없습니다.</p>
        )}
      </section>

      <section>
        <h3>재무 하이라이트</h3>
        <ul>
          {financialHighlights.map((h, i) => (
            <li key={i}>{h}</li>
          ))}
        </ul>
      </section>

      <section>
        <h3>최근 4분기 재무</h3>
        {quarterlyFinancials.length > 0 ? (
          <table className="snapshot-table">
            <thead>
              <tr>
                <th>Quarter</th>
                <th>Revenue</th>
                <th>Operating Income</th>
                <th>EPS</th>
              </tr>
            </thead>
            <tbody>
              {quarterlyFinancials.map((row) => (
                <tr key={row.quarter}>
                  <td>{row.quarter}</td>
                  <td>{row.revenue}</td>
                  <td>{row.operating_income}</td>
                  <td>{row.eps}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="empty">분기 재무 데이터가 없습니다.</p>
        )}
      </section>

      <section>
        <h3>리스크 / 체크포인트</h3>
        <ul>
          {riskItems.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </section>

      <section>
        <h3>데이터 스냅샷</h3>
        <DataSnapshot snapshot={analysis.data_snapshot} />
      </section>

      <section>
        <div className="timeline-header-row">
          <h3>종목 타임라인</h3>
          <div className="timeline-window-toggle">
            <button type="button" className={timelineWindow === '30' ? 'active' : ''} onClick={() => setTimelineWindow('30')}>30D</button>
            <button type="button" className={timelineWindow === '90' ? 'active' : ''} onClick={() => setTimelineWindow('90')}>90D</button>
          </div>
        </div>
        {timelineLoading ? (
          <p>Loading timeline...</p>
        ) : visibleTimeline.length > 0 ? (
          <ul className="timeline-list">
            {visibleTimeline.map((entry) => (
              <li key={`${entry.date}-${entry.price}`} className="timeline-item">
                <div className="timeline-item-head">
                  <strong>{entry.date}</strong>
                  <span>{entry.price} / {entry.daily_change}</span>
                </div>
                <div className="timeline-item-meta">
                  <span className={`tone-badge tone-${entry.news_tone?.label ?? 'neutral'}`}>
                    {entry.news_tone?.label ?? 'neutral'}
                  </span>
                  {entry.upcoming_events?.[0] && (
                    <span className="event-badge">
                      {entry.upcoming_events[0].label} D-{entry.upcoming_events[0].days_until}
                    </span>
                  )}
                </div>
                <p>{entry.signal_or_takeaway}</p>
                {entry.top_news_summary && (
                  entry.top_news_link ? (
                    <a href={entry.top_news_link} target="_blank" rel="noopener noreferrer">{entry.top_news_summary}</a>
                  ) : (
                    <p>{entry.top_news_summary}</p>
                  )
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty">타임라인 데이터가 없습니다.</p>
        )}
      </section>

      <section className="signal-conclusion">
        <h3>시그널 / 한줄 결론</h3>
        <p className="signal-text">{analysis.signal_or_takeaway}</p>
      </section>
    </div>
  )
}

function compareFilingsByDate(left: string, right: string, sort: FilingSort): number {
  const leftMs = parseFilingDate(left)
  const rightMs = parseFilingDate(right)
  if (sort === 'oldest') {
    return leftMs - rightMs
  }
  return rightMs - leftMs
}

function parseFilingDate(value: string): number {
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? 0 : parsed
}

function buildFilingImpactSummary(tag: string, title: string): string {
  const normalizedTitle = title.toLowerCase()

  if (tag === '실적') {
    if (normalizedTitle.includes('10-q') || normalizedTitle.includes('10-k') || normalizedTitle.includes('20-f')) {
      return '실적과 가이던스 해석에 따라 단기 주가 변동성이 커질 수 있는 공시입니다.'
    }
    return '실적 관련 수치와 경영진 코멘트가 투자 심리에 직접 영향을 줄 수 있습니다.'
  }

  if (tag === '배당') {
    return '배당 정책이나 배당락 일정 변화가 단기 수급과 주주환원 기대에 영향을 줄 수 있습니다.'
  }

  if (tag === '주주총회') {
    return '안건 내용과 주주환원 방향이 지배구조 기대감과 투자 심리에 영향을 줄 수 있습니다.'
  }

  if (normalizedTitle.includes('8-k') || normalizedTitle.includes('important')) {
    return '중요 사항 공시로 해석될 수 있어, 세부 내용에 따라 주가 민감도가 높아질 수 있습니다.'
  }

  return '추가 공시 세부 내용을 확인하면 단기 이슈가 실적과 수급에 미칠 영향을 더 명확히 볼 수 있습니다.'
}

function estimateFilingImpactLevel(tag: string, formType: string, title: string): FilingImpactLevel {
  const normalizedForm = formType.toUpperCase()
  const normalizedTitle = title.toLowerCase()

  if (tag === '실적' || normalizedForm === '10-Q' || normalizedForm === '10-K' || normalizedForm === '20-F') {
    return '높음'
  }
  if (tag === '배당' || tag === '주주총회' || normalizedForm === 'DEF 14A') {
    return '보통'
  }
  if (normalizedForm === '8-K' && normalizedTitle.includes('important')) {
    return '보통'
  }
  return '낮음'
}

function toImpactClassName(level: FilingImpactLevel): string {
  if (level === '높음') return 'high'
  if (level === '보통') return 'medium'
  return 'low'
}


