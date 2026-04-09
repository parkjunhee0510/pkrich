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
import { buildPositionSizingSummary, buildPriceActionTags, extractActionPlan, getLatestCatalystItem } from '../utils/trader'

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
  const signalHistory = (data?.signal_stats?.recent_signals ?? []).filter((row) => row.ticker === ticker).slice(0, 10)
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
  const earningsSetup = analysis?.earnings_setup
  const priceAction = analysis?.price_action
  const tradeFrame = analysis?.trade_frame
  const earningsSummaryCards = buildEarningsSummaryCards(earningsSetup)
  const positioningCards = buildPositioningCards(analysis?.fundamentals ?? {})
  const positionSizing = buildPositionSizing(analysis?.data_snapshot ?? {}, priceAction, analysis?.fundamentals ?? {})
  const dashboardSizing = analysis ? buildPositionSizingSummary(analysis, 10000) : { stopPrice: 'N/A', positionShares: 'N/A', riskReward: 'N/A' }
  const actionPlan = analysis ? extractActionPlan(analysis) : null
  const latestCatalyst = analysis ? getLatestCatalystItem(analysis) : null
  const priceActionTags = analysis ? buildPriceActionTags(analysis) : []
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
          {priceActionTags.length > 0 && (
            <div className="watchlist-chip-row">
              {priceActionTags.map((tag) => (
                <span key={tag} className="setup-tag">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="ticker-price-group">
          <span className="ticker-price">{analysis.data_snapshot['Price']}</span>
          <span style={{ color: changeColor(pct), fontWeight: 600, fontSize: '1.1rem' }}>
            {analysis.data_snapshot['Daily Change']}
          </span>
          <SignalBadge changePercent={pct} />
        </div>
      </div>

      {actionPlan && (
        <section className="dashboard-panel-section">
          <div className="section-header-with-kicker">
            <div>
              <h3>의사결정 보드</h3>
              <p className="section-kicker">방향, 진입존, 무효화, 다음 catalyst를 첫 화면에서 바로 확인하는 트레이더 요약</p>
            </div>
          </div>
          <div className="decision-board-grid">
            <div className="price-action-card">
              <span className="price-action-label">방향</span>
              <strong>{actionPlan.direction}</strong>
              <span className="price-action-subtext">{actionPlan.thesis}</span>
            </div>
            <div className="price-action-card">
              <span className="price-action-label">진입존</span>
              <strong>{actionPlan.entry}</strong>
              <span className="price-action-subtext">시그널 포맷 기준</span>
            </div>
            <div className="price-action-card">
              <span className="price-action-label">무효화</span>
              <strong>{actionPlan.invalidation}</strong>
              <span className="price-action-subtext">{tradeFrame?.watch_period ?? '관찰 기간 확인'}</span>
            </div>
            <div className="price-action-card">
              <span className="price-action-label">다음 Catalyst</span>
              <strong>{actionPlan.nextCatalyst}</strong>
              <span className="price-action-subtext">{latestCatalyst?.tag ?? '공시/뉴스 모니터링'}</span>
            </div>
            <div className="price-action-card">
              <span className="price-action-label">2ATR 스탑</span>
              <strong>{dashboardSizing.stopPrice}</strong>
              <span className="price-action-subtext">10,000 USD 기준 {dashboardSizing.positionShares}</span>
            </div>
            <div className="price-action-card">
              <span className="price-action-label">목표가 기준 R/R</span>
              <strong>{dashboardSizing.riskReward}</strong>
              <span className="price-action-subtext">{analysis.fundamentals?.analyst_target_price ?? '목표가 없음'}</span>
            </div>
          </div>
        </section>
      )}

      <section className="earnings-hero-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>실적 셋업</h3>
            <p className="section-kicker">트레이더가 먼저 보는 컨센서스 대비 체력과 다음 이벤트 타이밍</p>
          </div>
        </div>
        <div className="earnings-hero-grid">
          {earningsSummaryCards.map((card) => (
            <div key={card.label} className={`earnings-hero-card ${card.tone}`}>
              <span className="earnings-hero-label">{card.label}</span>
              <strong className="earnings-hero-value">{card.value}</strong>
              {card.chip && (
                <span className={`earnings-result-chip ${toBeatMissClassName(card.chipValue ?? card.chip)}`}>
                  {card.chip}
                </span>
              )}
              <p className="earnings-hero-note">{card.note}</p>
            </div>
          ))}
        </div>
      </section>

      {latestSecFiling && (
        <section className="latest-filing-card">
          <div className="latest-filing-head">
            <div>
              <h3>최신 공시</h3>
              <SecFilingBadges tags={latestSecFiling.tag ? [latestSecFiling.tag] : []} />
              {latestSecFiling.catalyst_type && (
                <span className={`filing-catalyst-badge catalyst-${latestSecFiling.catalyst_type}`}>
                  {latestSecFiling.catalyst_type} catalyst
                </span>
              )}
              {latestFilingImpactLevel && (
                <span className={`filing-impact-badge impact-${toImpactClassName(latestFilingImpactLevel)}`}>
                  예상 영향도 {latestFilingImpactLevel}
                </span>
              )}
            </div>
            <span className="news-meta">
              {latestSecFiling.source && `${latestSecFiling.source} · `}
              {latestSecFiling.form_type && `${latestSecFiling.form_type}${latestSecFiling.item_number ? ` Item ${latestSecFiling.item_number}` : ''} · `}
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
                {event.label} {event.date} (D-{event.days_until}{event.timing ? ` · ${event.timing}` : ''})
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
                    {filing.catalyst_type && (
                      <span className={`filing-catalyst-badge catalyst-${filing.catalyst_type}`}>
                        {filing.catalyst_type} catalyst
                      </span>
                    )}
                    {filing.form_type && <span className="filing-form-chip">{filing.form_type}</span>}
                    {filing.item_number && <span className="filing-form-chip">Item {filing.item_number}</span>}
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
        <h3>실적 컨센서스 디테일</h3>
        <div className="price-action-grid">
          <div className="price-action-card">
            <span className="price-action-label">Forward EPS</span>
            <strong>{earningsSetup?.forward_eps ?? 'N/A'}</strong>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">TTM EPS</span>
            <strong>{earningsSetup?.ttm_eps ?? 'N/A'}</strong>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">Forward vs TTM</span>
            <strong>{formatDirectionalPriceAction(earningsSetup?.forward_vs_ttm)}</strong>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">EPS Growth</span>
            <strong>{earningsSetup?.earnings_growth ?? 'N/A'}</strong>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">최근 분기 추정 EPS</span>
            <strong>{earningsSetup?.latest_estimated_eps ?? 'N/A'}</strong>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">최근 분기 결과</span>
            <strong className="earnings-setup-stack">
              <span>{earningsSetup?.latest_surprise_pct ?? 'N/A'}</span>
              <span className={`earnings-result-chip ${toBeatMissClassName(earningsSetup?.latest_beat_miss)}`}>
                {earningsSetup?.latest_beat_miss ?? 'N/A'}
              </span>
            </strong>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">다음 실적 체크포인트</span>
            <strong>{earningsSetup?.next_earnings_event ?? 'N/A'}</strong>
          </div>
        </div>
      </section>

      <section>
        <h3>가격 행동 맥락</h3>
        <div className="price-action-grid">
          <div className="price-action-card">
            <span className="price-action-label">ATR(14)</span>
            <strong>{formatPriceActionPair(priceAction?.atr_14d, priceAction?.atr_percent)}</strong>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">Relative Volume</span>
            <strong>{priceAction?.relative_volume ?? 'N/A'}</strong>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">Gap</span>
            <strong>{priceAction?.gap_percent ?? 'N/A'}</strong>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">vs SMA50</span>
            <strong>{formatDirectionalPriceAction(priceAction?.price_vs_sma50)}</strong>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">vs SMA200</span>
            <strong>{formatDirectionalPriceAction(priceAction?.price_vs_sma200)}</strong>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">52주 위치</span>
            <strong>{priceAction?.week52_position ?? 'N/A'}</strong>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">RS vs SPY(30D)</span>
            <strong>{priceAction?.rs_vs_spy ?? 'N/A'}</strong>
          </div>
        </div>
      </section>

      <section>
        <h3>포지셔닝 데이터</h3>
        <div className="price-action-grid">
          {positioningCards.map((card) => (
            <div key={card.label} className="price-action-card">
              <span className="price-action-label">{card.label}</span>
              <strong>{card.value}</strong>
              <span className="price-action-subtext">{card.note}</span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3>포지션 사이징 참고</h3>
        <div className="price-action-grid">
          <div className="price-action-card">
            <span className="price-action-label">1% 리스크 기준</span>
            <strong>{positionSizing.positionShares}</strong>
            <span className="price-action-subtext">10,000 USD 계좌 기준 예상 수량</span>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">2ATR 스탑</span>
            <strong>{positionSizing.stopPrice}</strong>
            <span className="price-action-subtext">{positionSizing.stopNote}</span>
          </div>
          <div className="price-action-card">
            <span className="price-action-label">리스크/리워드</span>
            <strong>{positionSizing.riskReward}</strong>
            <span className="price-action-subtext">애널리스트 목표가 기준</span>
          </div>
        </div>
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
                <th>EPS 추정</th>
                <th>서프라이즈</th>
                <th>결과</th>
              </tr>
            </thead>
            <tbody>
              {quarterlyFinancials.map((row) => (
                <tr key={row.quarter}>
                  <td>{row.quarter}</td>
                  <td>{row.revenue}</td>
                  <td>{row.operating_income}</td>
                  <td>{row.eps}</td>
                  <td>{row.estimated_eps ?? 'N/A'}</td>
                  <td>{row.surprise_pct ?? 'N/A'}</td>
                  <td>
                    <span className={`earnings-result-chip ${toBeatMissClassName(row.beat_miss)}`}>
                      {row.beat_miss ?? 'N/A'}
                    </span>
                  </td>
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
        <h3>트레이드 프레임</h3>
        <div className="trade-frame-grid">
          <div className="trade-frame-card bull">
            <span className="trade-frame-label">Bull</span>
            <p>{tradeFrame?.bull_scenario ?? 'N/A'}</p>
          </div>
          <div className="trade-frame-card base">
            <span className="trade-frame-label">Base</span>
            <p>{tradeFrame?.base_scenario ?? 'N/A'}</p>
          </div>
          <div className="trade-frame-card bear">
            <span className="trade-frame-label">Bear</span>
            <p>{tradeFrame?.bear_scenario ?? 'N/A'}</p>
          </div>
        </div>
        <div className="trade-frame-footer">
          <span><strong>무효화:</strong> {tradeFrame?.invalidation_price ?? 'N/A'}</span>
          <span><strong>관찰 기간:</strong> {tradeFrame?.watch_period ?? 'N/A'}</span>
        </div>
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

      <section>
        <h3>시그널 검증 이력</h3>
        {signalHistory.length > 0 ? (
          <ul className="timeline-list">
            {signalHistory.map((row, index) => (
              <li key={`${row.signal_date}-${row.ticker}-${index}`} className="timeline-item">
                <div className="timeline-item-head">
                  <strong>{row.signal_date}</strong>
                  <span>{row.signal_direction} / {row.signal_price}</span>
                </div>
                <div className="timeline-item-meta">
                  <span className="filing-form-chip">{row.catalyst_tag}</span>
                  <span className="period-badge">1D {row.return_1d}</span>
                  <span className="period-badge">5D {row.return_5d}</span>
                  <span className="period-badge">20D {row.return_20d}</span>
                </div>
                <p>{row.trade_frame_scenario}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty">아직 시그널 검증 이력이 없습니다.</p>
        )}
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

function formatPriceActionPair(primary?: string, secondary?: string): string {
  const base = primary?.trim() || 'N/A'
  const pct = secondary?.trim() || 'N/A'
  if (base === 'N/A' && pct === 'N/A') return 'N/A'
  if (pct === 'N/A') return base
  return `${base} (${pct})`
}

function formatDirectionalPriceAction(value?: string): string {
  const normalized = value?.trim() || 'N/A'
  if (normalized === 'N/A') return normalized
  const numeric = Number.parseFloat(normalized.replace('%', ''))
  if (Number.isNaN(numeric)) return normalized
  return `${normalized} (${numeric >= 0 ? '위' : '아래'})`
}

function toBeatMissClassName(value?: string): string {
  if (value === 'beat') return 'beat'
  if (value === 'miss') return 'miss'
  if (value === 'in-line') return 'inline'
  return 'na'
}

type EarningsCardTone = 'positive' | 'neutral' | 'caution' | 'negative'

type EarningsSummaryCard = {
  label: string
  value: string
  note: string
  tone: EarningsCardTone
  chip?: string
  chipValue?: string
}

function buildEarningsSummaryCards(earningsSetup?: {
  forward_eps?: string
  ttm_eps?: string
  forward_vs_ttm?: string
  earnings_growth?: string
  latest_estimated_eps?: string
  latest_surprise_pct?: string
  latest_beat_miss?: string
  next_earnings_event?: string
}): EarningsSummaryCard[] {
  const forwardVsTtm = earningsSetup?.forward_vs_ttm ?? 'N/A'
  const beatMiss = earningsSetup?.latest_beat_miss ?? 'N/A'
  const nextEvent = earningsSetup?.next_earnings_event ?? 'N/A'
  const dday = extractDday(nextEvent)

  return [
    {
      label: 'Forward vs TTM',
      value: forwardVsTtm,
      note: `${earningsSetup?.forward_eps ?? 'N/A'} vs ${earningsSetup?.ttm_eps ?? 'N/A'}`,
      tone: classifyDirectionalTone(forwardVsTtm),
    },
    {
      label: '최근 분기 결과',
      value: earningsSetup?.latest_surprise_pct ?? 'N/A',
      note: `컨센서스 EPS ${earningsSetup?.latest_estimated_eps ?? 'N/A'}`,
      tone: classifyBeatMissTone(beatMiss),
      chip: formatBeatMissLabel(beatMiss),
      chipValue: beatMiss,
    },
    {
      label: '다음 실적 D-day',
      value: dday,
      note: nextEvent,
      tone: classifyDdayTone(dday),
    },
    {
      label: 'EPS 성장률',
      value: earningsSetup?.earnings_growth ?? 'N/A',
      note: 'YoY 기준 이익 성장 체력',
      tone: classifyDirectionalTone(earningsSetup?.earnings_growth ?? 'N/A'),
    },
  ]
}

type PositioningCard = {
  label: string
  value: string
  note: string
}

type PositionSizingSummary = {
  positionShares: string
  stopPrice: string
  stopNote: string
  riskReward: string
}

function buildPositioningCards(fundamentals: Record<string, string>): PositioningCard[] {
  const shortFloat = fundamentals.short_float_pct ?? 'N/A'
  const shortRatio = fundamentals.short_ratio ?? 'N/A'
  const analystRecommendation = fundamentals.analyst_recommendation ?? 'N/A'
  const analystCount = fundamentals.analyst_count ?? 'N/A'
  const analystTarget = fundamentals.analyst_target_price ?? 'N/A'
  const insiders = fundamentals.held_by_insiders ?? 'N/A'
  const institutions = fundamentals.held_by_institutions ?? 'N/A'
  const impliedVolatility = fundamentals.implied_volatility ?? 'N/A'

  return [
    {
      label: '공매도',
      value: shortFloat,
      note: shortRatio !== 'N/A' ? `커버 ${shortRatio}` : '커버링 일수 미확인',
    },
    {
      label: '애널리스트',
      value: analystRecommendation,
      note: `${analystCount}, 목표 ${analystTarget}`,
    },
    {
      label: '스마트머니 보유',
      value: institutions,
      note: `내부자 ${insiders}`,
    },
    {
      label: '옵션 IV',
      value: impliedVolatility,
      note: '연환산 기준 내재변동성',
    },
  ]
}

function buildPositionSizing(
  snapshot: Record<string, string>,
  priceAction?: { atr_14d?: string },
  fundamentals?: Record<string, string>,
): PositionSizingSummary {
  const price = parseFirstNumber(snapshot['Price'])
  const atr = parseFirstNumber(priceAction?.atr_14d)
  const currency = extractCurrency(snapshot['Price'])
  if (price === null || atr === null || atr <= 0) {
    return {
      positionShares: 'N/A',
      stopPrice: 'N/A',
      stopNote: 'ATR 데이터 부족',
      riskReward: 'N/A',
    }
  }

  const stopDistance = atr * 2
  const stopPrice = price - stopDistance
  const positionShares = Math.floor(100 / atr)
  const analystTarget = parseFirstNumber(fundamentals?.analyst_target_price)
  let riskReward = 'N/A'
  if (analystTarget !== null && analystTarget > price && stopDistance > 0) {
    riskReward = `${((analystTarget - price) / stopDistance).toFixed(2)}R`
  }

  return {
    positionShares: `${positionShares}주`,
    stopPrice: `${stopPrice.toFixed(2)} ${currency}`,
    stopNote: `${price.toFixed(2)} ${currency} - ${stopDistance.toFixed(2)}`,
    riskReward,
  }
}

function formatBeatMissLabel(value?: string): string {
  if (value === 'beat') return 'BEAT'
  if (value === 'miss') return 'MISS'
  if (value === 'in-line') return 'IN-LINE'
  return 'N/A'
}

function classifyBeatMissTone(value?: string): EarningsCardTone {
  if (value === 'beat') return 'positive'
  if (value === 'miss') return 'negative'
  if (value === 'in-line') return 'neutral'
  return 'neutral'
}

function classifyDirectionalTone(value: string): EarningsCardTone {
  const numeric = Number.parseFloat(value.replace(/[^0-9+-.]/g, ''))
  if (Number.isNaN(numeric)) return 'neutral'
  if (numeric > 0) return 'positive'
  if (numeric < 0) return 'negative'
  return 'neutral'
}

function extractDday(value: string): string {
  const match = value.match(/D-(\d+)(?:\s*[·|]\s*([A-Z]+))?/)
  if (!match) return 'N/A'
  return match[2] ? `D-${match[1]} · ${match[2]}` : `D-${match[1]}`
}

function classifyDdayTone(value: string): EarningsCardTone {
  const numeric = Number.parseInt(value.replace('D-', ''), 10)
  if (Number.isNaN(numeric)) return 'neutral'
  if (numeric <= 7) return 'negative'
  if (numeric <= 21) return 'caution'
  return 'neutral'
}

function parseFirstNumber(value?: string): number | null {
  if (!value) return null
  const match = value.replace(/,/g, '').match(/[-+]?\d*\.?\d+/)
  if (!match) return null
  const numeric = Number.parseFloat(match[0])
  return Number.isNaN(numeric) ? null : numeric
}

function extractCurrency(value?: string): string {
  if (!value) return 'USD'
  const parts = value.trim().split(/\s+/)
  const tail = parts[parts.length - 1]
  return /^[A-Z]{3,5}$/.test(tail) ? tail : 'USD'
}


