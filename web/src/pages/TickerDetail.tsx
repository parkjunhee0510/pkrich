import { Suspense, lazy, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useDashboardData } from '../hooks/useDashboardData'
import { usePriceHistory } from '../hooks/usePriceHistory'
import { useTickerTimeline } from '../hooks/useTickerTimeline'
import { DataSnapshot } from '../components/DataSnapshot'
import { NewsItem } from '../components/NewsItem'
import { SecFilingBadges } from '../components/SecFilingBadges'
import { InfoTooltip } from '../components/InfoTooltip'
import { DecisionCard } from '../components/DecisionCard'
import { TraderDecisionBoard } from '../components/TraderDecisionBoard'
import { TickerDetailSkeleton } from '../components/Skeleton'
import { ErrorState } from '../components/ErrorState'
import type { SectorComparison, SignalHistoryEntry, SignalHistoryRow } from '../types'
import { parseNumericChange, changeColor } from '../utils/format'
import { EpsSurpriseChart } from '../components/EpsSurpriseChart'
import { buildPositionSizingSummary, buildPriceActionTags, extractActionPlan, getLatestCatalystItem } from '../utils/trader'

const HEADER_ENSEMBLE_BADGES: Record<string, { symbol: string; label: string; className: string }> = {
  agree: { symbol: '✓✓', label: '합의 일치', className: 'ticker-ensemble-badge-agree' },
  conflict: { symbol: '✓✗', label: '합의 불일치', className: 'ticker-ensemble-badge-conflict' },
  single: { symbol: '•', label: '단일 판단', className: 'ticker-ensemble-badge-single' },
}

const HEADER_SELECTION_REASON_LABELS: Record<string, string> = {
  selected: '2차 검토 완료',
  cap_exceeded: '2차 검토 대기',
  out_of_range: '재검토 범위 밖',
  disabled: '앙상블 비활성화',
}

const HEADER_FINAL_CONSENSUS_LABELS: Record<string, string> = {
  agree: '최종 합의 일치',
  resolved: '3차 검토로 합의',
  conflict: '3차 후에도 불일치',
  single: '단일 판단',
}

const NEWS_TONE_LABELS: Record<string, string> = {
  bullish: '강세',
  bearish: '약세',
  neutral: '중립',
}

const DECISION_ACTION_LABELS: Record<string, string> = {
  buy: '매수',
  watch: '관찰',
  avoid: '회피',
}

const FILING_TABS = ['실적', '배당', '주주총회', '기타 공시'] as const

type FilingTab = (typeof FILING_TABS)[number]
type FilingSort = 'latest' | 'oldest'
type FilingImpactLevel = '높음' | '보통' | '낮음'
type EarningsCardTone = 'positive' | 'neutral' | 'caution' | 'negative'

type EarningsSummaryCard = {
  label: string
  value: string
  note: string
  tone: EarningsCardTone
  chip?: string
  chipValue?: string
  tooltip?: ReactNode
}

type PositioningCard = {
  label: string
  value: string
  note: string
  tooltip?: ReactNode
}

type PositionSizingSummary = {
  positionShares: string
  stopPrice: string
  stopNote: string
  riskReward: string
}

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
  const fallbackSignalHistory = (data?.signal_stats?.recent_signals ?? []).filter((row) => row.ticker === ticker).slice(0, 10)
  const pct = parseNumericChange(analysis?.data_snapshot['Daily Change'] ?? '0')
  const visibleTimeline = useMemo(() => {
    const limit = timelineWindow === '30' ? 30 : 90
    return timelineEntries.slice(0, limit)
  }, [timelineEntries, timelineWindow])
  const upcomingEvents = analysis?.upcoming_events ?? []
  const newsReferences = analysis?.news_references ?? []
  const keyNews = analysis?.key_news ?? []
  const secFilings = useMemo(() => analysis?.sec_filings ?? [], [analysis?.sec_filings])
  const financialHighlights = analysis?.financial_highlights ?? []
  const riskItems = analysis?.risks_or_watchpoints ?? []
  const quarterlyFinancials = analysis?.quarterly_financials ?? []
  const earningsSetup = analysis?.earnings_setup
  const priceAction = analysis?.price_action
  const tradeFrame = analysis?.trade_frame
  const signalHistory = useMemo(
    () => normalizeSignalHistory(analysis?.signal_history, fallbackSignalHistory),
    [analysis?.signal_history, fallbackSignalHistory],
  )
  const sectorComparisonRows = useMemo(
    () => buildSectorComparisonRows(analysis?.sector_comparison),
    [analysis?.sector_comparison],
  )
  const earningsSummaryCards = buildEarningsSummaryCards(earningsSetup)
  const positioningCards = buildPositioningCards(analysis?.fundamentals ?? {})
  const positionSizing = buildPositionSizing(analysis?.data_snapshot ?? {}, priceAction, analysis?.fundamentals ?? {})
  const dashboardSizing = analysis
    ? buildPositionSizingSummary(analysis, 10000)
    : { stopPrice: 'N/A', positionShares: 'N/A', riskReward: 'N/A' }
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
          activeTabFilings.map((filing) => filing.form_type.trim()).filter((formType) => formType.length > 0),
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

  useEffect(() => {
    if (analysis) {
      document.title = `${analysis.ticker} · Stock Research`
    } else {
      document.title = 'Stock Research'
    }
  }, [analysis])

  if (loading) return <TickerDetailSkeleton />
  if (error) return <ErrorState message={error} />
  if (!data || !ticker) return <p className="status">No data available.</p>
  if (!analysis) return <p className="status">Ticker {ticker} not found.</p>
  const headerEnsemble = HEADER_ENSEMBLE_BADGES[analysis.decision?.ensemble_agreement ?? 'single'] ?? HEADER_ENSEMBLE_BADGES.single
  const headerSelectionReason = analysis.analysis_consensus?.selection_reason
    ? HEADER_SELECTION_REASON_LABELS[analysis.analysis_consensus.selection_reason] ?? analysis.analysis_consensus.selection_reason
    : null
  const headerThirdReviewCompleted = Boolean(analysis.analysis_consensus?.third_review_completed || analysis.analysis_consensus?.third_action)
  const headerFinalConsensus = analysis.decision?.final_consensus ?? analysis.analysis_consensus?.final_consensus ?? 'single'

  return (
    <div className="ticker-detail">
      <Link to="/" className="back-link">&larr; Dashboard</Link>

      <div className="ticker-header">
        <div>
          <h2>{analysis.ticker} · {analysis.name}</h2>
          <span className="ticker-date">{analysis.date}</span>
          <div className="ticker-meta-row">
            <span className={`tone-badge tone-${analysis.news_tone?.label ?? 'neutral'}`}>
              뉴스 톤: {NEWS_TONE_LABELS[analysis.news_tone?.label ?? 'neutral'] ?? '중립'}
            </span>
            {typeof analysis.news_tone?.confidence === 'number' ? (
              <span className="period-badge">{formatNewsToneConfidence(analysis.news_tone.confidence)}</span>
            ) : null}
            <span className={`period-badge ticker-ensemble-badge ${headerEnsemble.className}`}>
              {headerEnsemble.symbol} {headerEnsemble.label}
              <InfoTooltip
                content={
                  <span className="metric-tooltip-copy">
                    {headerSelectionReason ? (
                      <>
                        <strong>선정 사유</strong>
                        <span>{headerSelectionReason}</span>
                      </>
                    ) : null}
                    {analysis.decision?.ensemble_agreement === 'conflict' ? (
                      <>
                        <strong>1차 판단</strong>
                        <span>{DECISION_ACTION_LABELS[analysis.analysis_consensus?.economy_action ?? 'watch'] ?? '관찰'} - {analysis.analysis_consensus?.economy_reason ?? '사유 없음'}</span>
                        <strong>2차 판단</strong>
                        <span>{DECISION_ACTION_LABELS[analysis.analysis_consensus?.deep_action ?? analysis.decision?.action ?? 'watch'] ?? '관찰'} - {analysis.analysis_consensus?.deep_reason ?? analysis.decision?.reason ?? '사유 없음'}</span>
                        {headerThirdReviewCompleted ? (
                          <>
                            <strong>3차 판단</strong>
                            <span>{DECISION_ACTION_LABELS[analysis.analysis_consensus?.third_action ?? analysis.decision?.action ?? 'watch'] ?? '관찰'} - {analysis.analysis_consensus?.third_reason ?? '사유 없음'}</span>
                            <strong>최종 합의</strong>
                            <span>{HEADER_FINAL_CONSENSUS_LABELS[headerFinalConsensus] ?? headerFinalConsensus}</span>
                          </>
                        ) : null}
                      </>
                    ) : (
                      <>
                        <strong>합의 상태</strong>
                        <span>{headerEnsemble.label}</span>
                      </>
                    )}
                  </span>
                }
              />
            </span>
            {headerThirdReviewCompleted ? (
              <span className="period-badge ticker-third-review-badge">
                ③ 3차 검토 완료
                <InfoTooltip
                  content={
                    <span className="metric-tooltip-copy">
                      <strong>3차 판단</strong>
                      <span>{DECISION_ACTION_LABELS[analysis.analysis_consensus?.third_action ?? analysis.decision?.action ?? 'watch'] ?? '관찰'} - {analysis.analysis_consensus?.third_reason ?? '사유 없음'}</span>
                      <strong>최종 합의</strong>
                      <span>{HEADER_FINAL_CONSENSUS_LABELS[headerFinalConsensus] ?? headerFinalConsensus}</span>
                    </span>
                  }
                />
              </span>
            ) : null}
            <span className="period-badge">7D {analysis.period_changes?.['7d'] ?? 'N/A'}</span>
            <span className="period-badge">30D {analysis.period_changes?.['30d'] ?? 'N/A'}</span>
          </div>
          {analysis.news_tone?.reasoning ? (
            <p className="ticker-meta-explainer">{analysis.news_tone.reasoning}</p>
          ) : null}
          <SecFilingBadges tags={analysis.sec_filing_tags ?? []} />
          {priceActionTags.length > 0 && (
            <div className="watchlist-chip-row">
              {priceActionTags.map((tag) => (
                <span key={tag} className="setup-tag">{tag}</span>
              ))}
            </div>
          )}
        </div>
        <div className="ticker-price-group">
          <span className="ticker-price">{analysis.data_snapshot['Price']}</span>
          <span style={{ color: changeColor(pct), fontWeight: 600, fontSize: '1.1rem' }}>
            {analysis.data_snapshot['Daily Change']}
          </span>
        </div>
      </div>

      {analysis.decision && (
        <DecisionCard decision={analysis.decision} analysisConsensus={analysis.analysis_consensus} />
      )}

      {actionPlan && (
        <TraderDecisionBoard
          actionPlan={actionPlan}
          latestCatalyst={latestCatalyst}
          dashboardSizing={dashboardSizing}
          targetPrice={analysis.fundamentals?.analyst_target_price}
          tradeFrame={tradeFrame}
        />
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
              <span className="earnings-hero-label earnings-hero-label-row">
                <span>{card.label}</span>
                {card.tooltip ? <InfoTooltip content={card.tooltip} /> : null}
              </span>
              <strong className="earnings-hero-value">{card.value}</strong>
              {card.chip && (
                <span className={`earnings-result-chip ${toBeatMissClassName(card.chipValue ?? card.chip)}`}>{card.chip}</span>
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
          <p className="latest-filing-summary">{buildFilingImpactSummary(latestSecFiling.tag, latestSecFiling.title)}</p>
          {latestSecFiling.link && (
            <a href={latestSecFiling.link} target="_blank" rel="noopener noreferrer">공시 원문 보기</a>
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

      {(analysis.news_tone?.reasoning || typeof analysis.news_tone?.confidence === 'number') && (
        <ResponsiveDetailSection title="뉴스 톤 / 해석">
          <div className="detail-note-card">
            <div className="detail-note-row">
              <span className={`tone-badge tone-${analysis.news_tone?.label ?? 'neutral'}`}>
                {NEWS_TONE_LABELS[analysis.news_tone?.label ?? 'neutral'] ?? '중립'}
              </span>
              {typeof analysis.news_tone?.confidence === 'number' ? (
                <span className="period-badge">{formatNewsToneConfidence(analysis.news_tone.confidence)}</span>
              ) : null}
            </div>
            {analysis.news_tone?.reasoning ? <p>{analysis.news_tone.reasoning}</p> : null}
          </div>
        </ResponsiveDetailSection>
      )}

      <ResponsiveDetailSection title="다가오는 일정" defaultOpen>
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
      </ResponsiveDetailSection>

      <ResponsiveDetailSection title="주요 뉴스">
        {newsReferences.length > 0 ? (
          <ul className="news-list">
            {newsReferences.map((ref, i) => (
              <NewsItem key={i} item={ref} summary={keyNews[i]} />
            ))}
          </ul>
        ) : (
          <p className="empty">수집된 뉴스가 없습니다.</p>
        )}
      </ResponsiveDetailSection>

      <ResponsiveDetailSection title="공시자료">
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
                <select className="filing-form-filter" value={activeFormType} onChange={(event) => setSelectedFormType(event.target.value)}>
                  <option value="ALL">전체 폼</option>
                  {availableFormTypes.map((formType) => (
                    <option key={formType} value={formType}>{formType}</option>
                  ))}
                </select>
                <div className="filing-sort-toggle" role="group" aria-label="filing sort">
                  <button type="button" className={filingSort === 'latest' ? 'active' : ''} onClick={() => setFilingSort('latest')}>최신순</button>
                  <button type="button" className={filingSort === 'oldest' ? 'active' : ''} onClick={() => setFilingSort('oldest')}>날짜순</button>
                </div>
              </div>
            </div>
            {visibleSecFilings.length > 0 ? (
              <ul className="news-list">
                {visibleSecFilings.map((filing, index) => (
                  <li key={`${filing.published_at}-${filing.title}-${index}`} className="news-item">
                    <SecFilingBadges tags={filing.tag ? [filing.tag] : []} />
                    {filing.catalyst_type && <span className={`filing-catalyst-badge catalyst-${filing.catalyst_type}`}>{filing.catalyst_type} catalyst</span>}
                    {filing.form_type && <span className="filing-form-chip">{filing.form_type}</span>}
                    {filing.item_number && <span className="filing-form-chip">Item {filing.item_number}</span>}
                    {filing.link ? (
                      <a href={filing.link} target="_blank" rel="noopener noreferrer">{filing.title}</a>
                    ) : (
                      <span>{filing.title}</span>
                    )}
                    <span className="news-meta">{filing.source && ` · ${filing.source}`}{filing.published_at && ` (${filing.published_at})`}</span>
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
      </ResponsiveDetailSection>

      <ResponsiveDetailSection title="재무 하이라이트">
        <ul>
          {financialHighlights.map((h, i) => (
            <li key={i}>{h}</li>
          ))}
        </ul>
      </ResponsiveDetailSection>

      <ResponsiveDetailSection title="실적 컨센서스 디테일">
        <div className="price-action-grid">
          <DetailMetricCard label="Forward EPS" value={earningsSetup?.forward_eps ?? 'N/A'} tooltip={METRIC_TOOLTIPS.forwardEps} />
          <DetailMetricCard label="TTM EPS" value={earningsSetup?.ttm_eps ?? 'N/A'} tooltip={METRIC_TOOLTIPS.ttmEps} />
          <DetailMetricCard label="Forward vs TTM" value={formatDirectionalPriceAction(earningsSetup?.forward_vs_ttm)} tooltip={METRIC_TOOLTIPS.forwardVsTtm} />
          <DetailMetricCard label="EPS Growth" value={earningsSetup?.earnings_growth ?? 'N/A'} tooltip={METRIC_TOOLTIPS.epsGrowth} />
          <DetailMetricCard label="최근 분기 추정 EPS" value={earningsSetup?.latest_estimated_eps ?? 'N/A'} tooltip={METRIC_TOOLTIPS.latestEstimatedEps} />
          <DetailMetricCard
            label="최근 분기 결과"
            tooltip={METRIC_TOOLTIPS.latestQuarterResult}
            value={
              <strong className="earnings-setup-stack">
                <span>{earningsSetup?.latest_surprise_pct ?? 'N/A'}</span>
                <span className={`earnings-result-chip ${toBeatMissClassName(earningsSetup?.latest_beat_miss)}`}>{earningsSetup?.latest_beat_miss ?? 'N/A'}</span>
              </strong>
            }
          />
          <DetailMetricCard label="다음 실적 체크포인트" value={earningsSetup?.next_earnings_event ?? 'N/A'} tooltip={METRIC_TOOLTIPS.nextEarningsEvent} />
        </div>
      </ResponsiveDetailSection>
      <ResponsiveDetailSection title="가격 행동 맥락">
        <div className="price-action-grid">
          <DetailMetricCard label="ATR(14)" value={formatPriceActionPair(priceAction?.atr_14d, priceAction?.atr_percent)} tooltip={METRIC_TOOLTIPS.atr14} />
          <DetailMetricCard label="Relative Volume" value={priceAction?.relative_volume ?? 'N/A'} tooltip={METRIC_TOOLTIPS.relativeVolume} />
          <DetailMetricCard label="Gap" value={priceAction?.gap_percent ?? 'N/A'} tooltip={METRIC_TOOLTIPS.gapPercent} />
          <DetailMetricCard label="vs SMA50" value={formatDirectionalPriceAction(priceAction?.price_vs_sma50)} tooltip={METRIC_TOOLTIPS.vsSma50} />
          <DetailMetricCard label="vs SMA200" value={formatDirectionalPriceAction(priceAction?.price_vs_sma200)} tooltip={METRIC_TOOLTIPS.vsSma200} />
          <DetailMetricCard label="52주 위치" value={priceAction?.week52_position ?? 'N/A'} tooltip={METRIC_TOOLTIPS.week52Position} />
          <DetailMetricCard label="RS vs SPY(30D)" value={priceAction?.rs_vs_spy ?? 'N/A'} tooltip={METRIC_TOOLTIPS.rsVsSpy} />
        </div>
      </ResponsiveDetailSection>

      <ResponsiveDetailSection title="포지셔닝 데이터">
        <div className="price-action-grid">
          {positioningCards.map((card) => (
            <DetailMetricCard key={card.label} label={card.label} value={card.value} note={card.note} tooltip={card.tooltip} />
          ))}
        </div>
      </ResponsiveDetailSection>

      {analysis.options_summary && Object.keys(analysis.options_summary).length > 0 && (
        <ResponsiveDetailSection title="옵션 요약">
          <div className="price-action-grid">
            <DetailMetricCard label="가장 가까운 만기" value={analysis.options_summary.expiry ?? 'N/A'} tooltip={METRIC_TOOLTIPS.nearestExpiry} />
            <DetailMetricCard label="ATM Call IV" value={analysis.options_summary.atm_call_iv ?? 'N/A'} tooltip={METRIC_TOOLTIPS.atmCallIv} />
            <DetailMetricCard label="ATM Put IV" value={analysis.options_summary.atm_put_iv ?? 'N/A'} tooltip={METRIC_TOOLTIPS.atmPutIv} />
            <DetailMetricCard label="Put/Call Ratio" value={analysis.options_summary.put_call_ratio ?? 'N/A'} tooltip={METRIC_TOOLTIPS.putCallRatio} />
            <DetailMetricCard label="30D IV Percentile" value={analysis.options_summary.iv_percentile_30d ?? 'N/A'} tooltip={METRIC_TOOLTIPS.ivPercentile30d} />
          </div>
        </ResponsiveDetailSection>
      )}

      <ResponsiveDetailSection title="포지션 사이징 참고">
        <div className="price-action-grid">
          <DetailMetricCard label="1% 리스크 기준" value={positionSizing.positionShares} note="10,000 USD 계좌 기준 예상 수량" tooltip={METRIC_TOOLTIPS.positionSizing1pct} />
          <DetailMetricCard label="2ATR 스탑" value={positionSizing.stopPrice} note={positionSizing.stopNote} tooltip={METRIC_TOOLTIPS.stopByAtr} />
          <DetailMetricCard label="리스크/리워드" value={positionSizing.riskReward} note="애널리스트 목표가 기준" tooltip={METRIC_TOOLTIPS.riskReward} />
        </div>
      </ResponsiveDetailSection>

      {analysis.valuation_score?.score && (
        <ResponsiveDetailSection title="밸류에이션 점수">
          <div className="valuation-score-panel">
            <div className="valuation-score-header">
              <span className={`valuation-score-badge ${getValuationScoreClass(analysis.valuation_score.score)}`}>
                {analysis.valuation_score.score}
              </span>
              <span className="valuation-score-label">{getValuationLabel(analysis.valuation_score.score)}</span>
            </div>
            {analysis.valuation_score.factors?.length > 0 && (
              <ul className="valuation-factors">
                {analysis.valuation_score.factors.map((factor, i) => (
                  <li key={i}>{factor}</li>
                ))}
              </ul>
            )}
            {analysis.valuation_score.assessment && (
              <p className="detail-section-summary">{analysis.valuation_score.assessment}</p>
            )}
          </div>
        </ResponsiveDetailSection>
      )}

      {sectorComparisonRows.length > 0 && (
        <ResponsiveDetailSection title="피어 비교">
          <div className="price-action-grid">
            {sectorComparisonRows.map((row) => (
              <div key={row.label} className="price-action-card">
                <span className="price-action-label">{row.label}</span>
                <strong>{row.company}</strong>
                <span className="price-action-subtext">Peer 평균 {row.peerAverage}</span>
                {row.difference ? <span className="price-action-subtext">격차 {row.difference}</span> : null}
              </div>
            ))}
          </div>
          {analysis.sector_comparison?.summary ? <p className="detail-section-summary">{analysis.sector_comparison.summary}</p> : null}
        </ResponsiveDetailSection>
      )}

      <ResponsiveDetailSection title="최근 4분기 재무">
        {quarterlyFinancials.length > 0 ? (
          <>
            <EpsSurpriseChart quarters={quarterlyFinancials} />
            <table className="snapshot-table">
              <thead>
                <tr>
                  <th>Quarter</th><th>Revenue</th><th>Operating Income</th><th>EPS</th><th>EPS 추정</th><th>서프라이즈</th><th>결과</th>
                </tr>
              </thead>
              <tbody>
                {quarterlyFinancials.map((row) => (
                  <tr key={row.quarter}>
                    <td>{row.quarter}</td><td>{row.revenue}</td><td>{row.operating_income}</td><td>{row.eps}</td><td>{row.estimated_eps ?? 'N/A'}</td><td>{row.surprise_pct ?? 'N/A'}</td>
                    <td><span className={`earnings-result-chip ${toBeatMissClassName(row.beat_miss)}`}>{row.beat_miss ?? 'N/A'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="empty">분기 재무 데이터가 없습니다.</p>
        )}
      </ResponsiveDetailSection>

      <ResponsiveDetailSection title="리스크 / 체크포인트">
        <ul>
          {riskItems.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </ResponsiveDetailSection>

      <ResponsiveDetailSection title="데이터 스냅샷">
        <DataSnapshot snapshot={analysis.data_snapshot} />
      </ResponsiveDetailSection>

      <ResponsiveDetailSection title="트레이드 프레임">
        <div className="trade-frame-grid">
          <div className="trade-frame-card bull"><span className="trade-frame-label">Bull</span><p>{tradeFrame?.bull_scenario ?? 'N/A'}</p></div>
          <div className="trade-frame-card base"><span className="trade-frame-label">Base</span><p>{tradeFrame?.base_scenario ?? 'N/A'}</p></div>
          <div className="trade-frame-card bear"><span className="trade-frame-label">Bear</span><p>{tradeFrame?.bear_scenario ?? 'N/A'}</p></div>
        </div>
        <div className="trade-frame-detail-grid">
          <DetailMetricCard label="진입가" value={tradeFrame?.entry_price ?? actionPlan?.entry ?? 'N/A'} tooltip={METRIC_TOOLTIPS.entryPrice} />
          <DetailMetricCard label="손절가" value={tradeFrame?.stop_loss ?? tradeFrame?.invalidation_price ?? 'N/A'} tooltip={METRIC_TOOLTIPS.stopLoss} />
          <DetailMetricCard label="목표가" value={[tradeFrame?.target_1, tradeFrame?.target_2].filter(Boolean).join(' / ') || 'N/A'} tooltip={METRIC_TOOLTIPS.targetPrice} />
          <DetailMetricCard label="R / R" value={tradeFrame?.risk_reward_ratio ?? dashboardSizing.riskReward} note={tradeFrame?.position_size_note ?? dashboardSizing.positionShares} tooltip={METRIC_TOOLTIPS.riskReward} />
        </div>
        <div className="trade-frame-footer">
          <span><strong>무효화:</strong> {tradeFrame?.invalidation_price ?? 'N/A'}</span>
          <span><strong>관찰 기간:</strong> {tradeFrame?.watch_period ?? 'N/A'}</span>
        </div>
      </ResponsiveDetailSection>

      <ResponsiveDetailSection title="종목 타임라인">
        <div className="timeline-header-row">
          <div />
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
                <div className="timeline-item-head"><strong>{entry.date}</strong><span>{entry.price} / {entry.daily_change}</span></div>
                <div className="timeline-item-meta">
                  <span className={`tone-badge tone-${entry.news_tone?.label ?? 'neutral'}`}>{NEWS_TONE_LABELS[entry.news_tone?.label ?? 'neutral'] ?? '중립'}</span>
                  {entry.upcoming_events?.[0] && <span className="event-badge">{entry.upcoming_events[0].label} D-{entry.upcoming_events[0].days_until}</span>}
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
      </ResponsiveDetailSection>

      <section className="signal-conclusion">
        <h3>시그널 / 한줄 결론</h3>
        <p className="signal-text">{analysis.signal_or_takeaway}</p>
      </section>

      <ResponsiveDetailSection title="시그널 검증 이력">
        {signalHistory.length > 0 ? (
          <ul className="timeline-list">
            {signalHistory.map((row, index) => (
              <li key={`${row.date}-${row.direction}-${index}`} className="timeline-item">
                <div className="timeline-item-head"><strong>{row.date}</strong><span>{row.direction}</span></div>
                <div className="timeline-item-meta">
                  <span className="filing-form-chip">{row.catalyst}</span>
                  {row.return5d ? <span className="period-badge">5D {row.return5d}</span> : null}
                </div>
                {row.note ? <p>{row.note}</p> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty">아직 시그널 검증 이력이 없습니다.</p>
        )}
      </ResponsiveDetailSection>
    </div>
  )
}

function ResponsiveDetailSection({ title, children, defaultOpen = false }: { title: string; children: ReactNode; defaultOpen?: boolean }) {
  const [isMobile, setIsMobile] = useState(false)
  const [isOpen, setIsOpen] = useState(defaultOpen)

  useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 768px)')
    const sync = () => {
      const mobile = mediaQuery.matches
      setIsMobile(mobile)
      setIsOpen(mobile ? defaultOpen : true)
    }
    sync()
    if (typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', sync)
      return () => mediaQuery.removeEventListener('change', sync)
    }
    mediaQuery.addListener(sync)
    return () => mediaQuery.removeListener(sync)
  }, [defaultOpen])

  if (!isMobile) {
    return <section className="ticker-detail-section-shell"><h3>{title}</h3>{children}</section>
  }

  return (
    <section className="ticker-detail-section-shell mobile-collapsible-section">
      <details className="ticker-detail-collapsible" open={isOpen} onToggle={(event) => setIsOpen((event.currentTarget as HTMLDetailsElement).open)}>
        <summary>
          <h3>{title}</h3>
          <span className="collapsible-chevron" aria-hidden="true">{isOpen ? '−' : '+'}</span>
        </summary>
        <div className="ticker-detail-section-body">{children}</div>
      </details>
    </section>
  )
}

function DetailMetricCard({
  label,
  value,
  note,
  tooltip,
}: {
  label: string
  value: ReactNode
  note?: string
  tooltip?: ReactNode
}) {
  return (
    <div className="price-action-card">
      <span className="price-action-label price-action-label-row">
        <span>{label}</span>
        {tooltip ? <InfoTooltip content={tooltip} /> : null}
      </span>
      {typeof value === 'string' ? <strong>{value}</strong> : value}
      {note ? <span className="price-action-subtext">{note}</span> : null}
    </div>
  )
}

const METRIC_TOOLTIPS = {
  forwardEps: (
    <span className="metric-tooltip-copy">
      <strong>Forward EPS</strong>
      시장이 앞으로 벌 거라고 보는 이익입니다. TTM EPS보다 높으면 "앞으로 더 좋아질 것"이라는 기대가 들어간 상태이고, 너무 높으면 기대가 과열됐을 수 있습니다.
    </span>
  ),
  ttmEps: (
    <span className="metric-tooltip-copy">
      <strong>TTM EPS</strong>
      지난 12개월 동안 실제로 벌어들인 이익입니다. 쉽게 말해 지금까지 확인된 실적 체력이고, Forward EPS와 같이 보면 기대가 현실보다 앞서 있는지 판단하기 좋습니다.
    </span>
  ),
  forwardVsTtm: (
    <span className="metric-tooltip-copy">
      <strong>Forward vs TTM</strong>
      앞으로의 이익 기대가 현재 실적보다 얼마나 센지 보여줍니다. 크게 플러스면 성장 기대가 강한 종목이고, 너무 과하면 실적 발표 때 눈높이 미달 리스크가 커집니다.
    </span>
  ),
  epsGrowth: (
    <span className="metric-tooltip-copy">
      <strong>EPS Growth</strong>
      이익이 전년보다 얼마나 늘었는지 보는 숫자입니다. 플러스가 이어지면 실적 추세가 좋다고 볼 수 있고, 마이너스가 커지면 밸류에이션 부담이 커질 수 있습니다.
    </span>
  ),
  latestEstimatedEps: (
    <span className="metric-tooltip-copy">
      <strong>최근 분기 추정 EPS</strong>
      시장이 직전 분기에 기대했던 숫자입니다. 실제 결과가 이걸 넘었는지 못 미쳤는지에 따라 실적 반응의 출발점이 결정됩니다.
    </span>
  ),
  latestQuarterResult: (
    <span className="metric-tooltip-copy">
      <strong>최근 분기 결과</strong>
      직전 실적이 기대치를 넘겼는지 보여줍니다. beat가 반복되면 매수 쪽 심리가 붙기 쉽고, miss가 이어지면 좋은 뉴스에도 주가가 둔하게 반응할 수 있습니다.
    </span>
  ),
  nextEarningsEvent: (
    <span className="metric-tooltip-copy">
      <strong>다음 실적 체크포인트</strong>
      다음 실적 발표 일정입니다. 날짜가 가까울수록 기대와 불안이 같이 커져서, 방향이 맞아도 변동성이 훨씬 거칠어질 수 있습니다.
    </span>
  ),
  atr14: (
    <span className="metric-tooltip-copy">
      <strong>ATR(14)</strong>
      최근 14일 동안 하루에 평균 얼마나 흔들렸는지를 보여줍니다. ATR이 크면 손절을 넓게 잡아야 하고, 같은 금액을 넣더라도 수량은 줄여서 들어가는 게 보통 더 안전합니다.
    </span>
  ),
  relativeVolume: (
    <span className="metric-tooltip-copy">
      <strong>Relative Volume</strong>
      오늘 거래량이 평소보다 얼마나 강한지 보는 숫자입니다. 1배를 크게 넘으면 "진짜 돈이 붙었다"는 해석이 가능하고, 낮으면 움직임이 나와도 신뢰도가 떨어질 수 있습니다.
    </span>
  ),
  gapPercent: (
    <span className="metric-tooltip-copy">
      <strong>Gap</strong>
      시가가 전일 종가보다 얼마나 위나 아래에서 시작했는지입니다. 큰 갭은 뉴스가 가격에 바로 반영됐다는 뜻이고, 갭을 메우는지 유지하는지가 당일 강도를 판단하는 포인트입니다.
    </span>
  ),
  vsSma50: (
    <span className="metric-tooltip-copy">
      <strong>vs SMA50</strong>
      현재가가 50일선보다 얼마나 위나 아래에 있는지입니다. 단기 추세가 살아 있는지 보는 기준이고, 50일선 이탈은 단기 모멘텀 약화 신호로 자주 해석됩니다.
    </span>
  ),
  vsSma200: (
    <span className="metric-tooltip-copy">
      <strong>vs SMA200</strong>
      현재가가 200일선보다 얼마나 위나 아래에 있는지입니다. 장기 추세의 기준선이라서, 200일선 위에 있으면 구조적으로 강한 종목으로 보는 경우가 많습니다.
    </span>
  ),
  week52Position: (
    <span className="metric-tooltip-copy">
      <strong>52주 위치</strong>
      현재가가 지난 1년 범위에서 어디쯤 있는지 보여줍니다. 높을수록 강한 추세일 수 있지만, 동시에 고점 부담과 차익실현 매물도 의식해야 합니다.
    </span>
  ),
  rsVsSpy: (
    <span className="metric-tooltip-copy">
      <strong>RS vs SPY(30D)</strong>
      최근 30일 동안 시장보다 더 강했는지 보는 비교 수치입니다. 플러스면 시장보다 잘 버티거나 더 강하게 오른 종목이고, 리더주인지 확인할 때 유용합니다.
    </span>
  ),
  shortFloat: (
    <span className="metric-tooltip-copy">
      <strong>공매도</strong>
      시장에서 이 종목 하락에 베팅한 물량 비중입니다. 높으면 악재에 취약할 수 있지만, 반대로 예상 밖 호재가 나오면 숏 스퀴즈가 강하게 나올 수도 있습니다.
    </span>
  ),
  analystRating: (
    <span className="metric-tooltip-copy">
      <strong>애널리스트</strong>
      시장의 평균 기대와 목표가 수준입니다. 이 숫자 자체보다, 최근에 상향이 이어지는지 하향이 늘어나는지를 보는 쪽이 실전에 더 도움이 됩니다.
    </span>
  ),
  smartMoneyOwnership: (
    <span className="metric-tooltip-copy">
      <strong>스마트머니 보유</strong>
      기관과 내부자가 얼마나 들고 있는지 보는 항목입니다. 기관 비중이 높으면 수급이 안정적인 편이고, 내부자 보유가 높으면 경영진이 회사 가치와 더 밀접하게 묶여 있다고 볼 수 있습니다.
    </span>
  ),
  optionIv: (
    <span className="metric-tooltip-copy">
      <strong>옵션 IV</strong>
      옵션 시장이 예상하는 앞으로의 흔들림입니다. IV가 높으면 방향을 맞혀도 등락이 크기 때문에, 진입 타이밍과 손절 폭을 더 보수적으로 잡는 편이 좋습니다.
    </span>
  ),
  nearestExpiry: (
    <span className="metric-tooltip-copy">
      <strong>가장 가까운 만기</strong>
      가장 빨리 도래하는 옵션 만기입니다. 만기가 가까우면 작은 움직임에도 수급이 예민하게 반응해서 단기 변동성이 커질 수 있습니다.
    </span>
  ),
  atmCallIv: (
    <span className="metric-tooltip-copy">
      <strong>ATM Call IV</strong>
      현재가 근처 콜옵션에 반영된 기대 변동성입니다. 콜 IV가 빠르게 오르면 상승 기대나 이벤트 앞둔 투기 수요가 붙는 경우가 많습니다.
    </span>
  ),
  atmPutIv: (
    <span className="metric-tooltip-copy">
      <strong>ATM Put IV</strong>
      현재가 근처 풋옵션에 반영된 기대 변동성입니다. 풋 IV가 높아지면 하락 방어 수요가 커지고 있다는 뜻으로 볼 수 있습니다.
    </span>
  ),
  putCallRatio: (
    <span className="metric-tooltip-copy">
      <strong>Put/Call Ratio</strong>
      풋 대비 콜이 얼마나 거래됐는지 보는 비율입니다. 낮으면 낙관적 베팅, 높으면 방어적이거나 하락 쪽 대비가 강하다고 해석하는 경우가 많습니다.
    </span>
  ),
  ivPercentile30d: (
    <span className="metric-tooltip-copy">
      <strong>30D IV Percentile</strong>
      최근 30일 기준으로 지금 IV가 높은 편인지 낮은 편인지 보여줍니다. 높으면 옵션 가격이 비싼 구간일 수 있고, 이벤트 기대가 과열됐는지도 같이 봐야 합니다.
    </span>
  ),
  positionSizing1pct: (
    <span className="metric-tooltip-copy">
      <strong>1% 리스크 기준</strong>
      한 번 틀렸을 때 계좌 손실을 1% 안쪽으로 제한한다고 가정한 수량입니다. 좋은 종목이라도 손절 폭이 넓으면 비중을 줄여야 오래 살아남을 수 있습니다.
    </span>
  ),
  stopByAtr: (
    <span className="metric-tooltip-copy">
      <strong>2ATR 스탑</strong>
      평균 변동폭의 2배 정도를 손절 거리로 잡은 예시입니다. 너무 타이트한 손절로 흔들림에 잘리지 않도록, 변동성이 큰 종목에 여유를 주는 방식입니다.
    </span>
  ),
  riskReward: (
    <span className="metric-tooltip-copy">
      <strong>리스크/리워드</strong>
      손절까지 감수하는 손실 대비, 목표가까지 기대하는 보상의 비율입니다. 보통 숫자가 높을수록 좋지만, 도달 가능성이 낮은 과한 목표는 의미가 약합니다.
    </span>
  ),
  entryPrice: (
    <span className="metric-tooltip-copy">
      <strong>진입가</strong>
      어디에서 들어갈지 정하는 가격대입니다. 같은 종목이라도 진입가가 나쁘면 손절은 멀어지고 기대수익은 줄어들어서 전체 매매가 불리해질 수 있습니다.
    </span>
  ),
  stopLoss: (
    <span className="metric-tooltip-copy">
      <strong>손절가</strong>
      내 시나리오가 틀렸다고 인정하는 가격입니다. 손절은 예측 실패의 확인선이지, 희망으로 버티는 구간이 아니라는 점이 중요합니다.
    </span>
  ),
  targetPrice: (
    <span className="metric-tooltip-copy">
      <strong>목표가</strong>
      수익 실현을 고려하는 가격대입니다. 너무 멀면 도달 확률이 떨어지고, 너무 짧으면 좋은 추세를 놓칠 수 있어서 저항선과 기대치의 균형이 중요합니다.
    </span>
  ),
} satisfies Record<string, ReactNode>
function compareFilingsByDate(left: string, right: string, sort: FilingSort): number {
  const leftMs = parseFilingDate(left)
  const rightMs = parseFilingDate(right)
  if (sort === 'oldest') return leftMs - rightMs
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
  if (tag === '배당') return '배당 정책이나 배당락 일정 변화가 단기 수급과 주주환원 기대에 영향을 줄 수 있습니다.'
  if (tag === '주주총회') return '안건 내용과 주주환원 방향이 지배구조 기대감과 투자 심리에 영향을 줄 수 있습니다.'
  if (normalizedTitle.includes('8-k') || normalizedTitle.includes('important')) {
    return '중요 사항 공시로 해석될 수 있어, 세부 내용에 따라 주가 민감도가 높아질 수 있습니다.'
  }
  return '추가 공시 세부 내용을 확인하면 단기 이슈가 실적과 수급에 미칠 영향을 더 명확히 볼 수 있습니다.'
}

function estimateFilingImpactLevel(tag: string, formType: string, title: string): FilingImpactLevel {
  const normalizedForm = formType.toUpperCase()
  const normalizedTitle = title.toLowerCase()
  if (tag === '실적' || normalizedForm === '10-Q' || normalizedForm === '10-K' || normalizedForm === '20-F') return '높음'
  if (tag === '배당' || tag === '주주총회' || normalizedForm === 'DEF 14A') return '보통'
  if (normalizedForm === '8-K' && normalizedTitle.includes('important')) return '보통'
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
    { label: 'Forward vs TTM', value: forwardVsTtm, note: `${earningsSetup?.forward_eps ?? 'N/A'} vs ${earningsSetup?.ttm_eps ?? 'N/A'}`, tone: classifyDirectionalTone(forwardVsTtm), tooltip: METRIC_TOOLTIPS.forwardVsTtm },
    { label: '최근 분기 결과', value: earningsSetup?.latest_surprise_pct ?? 'N/A', note: `컨센서스 EPS ${earningsSetup?.latest_estimated_eps ?? 'N/A'}`, tone: classifyBeatMissTone(beatMiss), chip: formatBeatMissLabel(beatMiss), chipValue: beatMiss, tooltip: METRIC_TOOLTIPS.latestQuarterResult },
    { label: '다음 실적 D-day', value: dday, note: nextEvent, tone: classifyDdayTone(dday), tooltip: METRIC_TOOLTIPS.nextEarningsEvent },
    { label: 'EPS 성장률', value: earningsSetup?.earnings_growth ?? 'N/A', note: 'YoY 기준 이익 성장 체력', tone: classifyDirectionalTone(earningsSetup?.earnings_growth ?? 'N/A'), tooltip: METRIC_TOOLTIPS.epsGrowth },
  ]
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
    { label: '공매도', value: shortFloat, note: shortRatio !== 'N/A' ? `커버 ${shortRatio}` : '커버링 일수 미확인', tooltip: METRIC_TOOLTIPS.shortFloat },
    { label: '애널리스트', value: analystRecommendation, note: `${analystCount}, 목표 ${analystTarget}`, tooltip: METRIC_TOOLTIPS.analystRating },
    { label: '스마트머니 보유', value: institutions, note: `내부자 ${insiders}`, tooltip: METRIC_TOOLTIPS.smartMoneyOwnership },
    { label: '옵션 IV', value: impliedVolatility, note: '연환산 기준 내재변동성', tooltip: METRIC_TOOLTIPS.optionIv },
  ]
}

function buildPositionSizing(snapshot: Record<string, string>, priceAction?: { atr_14d?: string }, fundamentals?: Record<string, string>): PositionSizingSummary {
  const price = parseFirstNumber(snapshot['Price'])
  const atr = parseFirstNumber(priceAction?.atr_14d)
  const currency = extractCurrency(snapshot['Price'])
  if (price === null || atr === null || atr <= 0) {
    return { positionShares: 'N/A', stopPrice: 'N/A', stopNote: 'ATR 데이터 부족', riskReward: 'N/A' }
  }
  const stopDistance = atr * 2
  const stopPrice = price - stopDistance
  const positionShares = Math.floor(100 / atr)
  const analystTarget = parseFirstNumber(fundamentals?.analyst_target_price)
  let riskReward = 'N/A'
  if (analystTarget !== null && analystTarget > price && stopDistance > 0) {
    riskReward = `${((analystTarget - price) / stopDistance).toFixed(2)}R`
  }
  return { positionShares: `${positionShares}주`, stopPrice: `${stopPrice.toFixed(2)} ${currency}`, stopNote: `${price.toFixed(2)} ${currency} - ${stopDistance.toFixed(2)}`, riskReward }
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

function formatNewsToneConfidence(confidence: number): string {
  const normalized = Math.max(1, Math.min(5, Math.round(confidence)))
  const percentage = normalized * 20
  const levelMap: Record<number, string> = {
    1: '낮음',
    2: '보통',
    3: '높음',
    4: '매우 높음',
    5: '매우 높음',
  }
  return `신뢰도 ${levelMap[normalized]} (${percentage}%)`
}

function extractCurrency(value?: string): string {
  if (!value) return 'USD'
  const parts = value.trim().split(/\s+/)
  const tail = parts[parts.length - 1]
  return /^[A-Z]{3,5}$/.test(tail) ? tail : 'USD'
}

type NormalizedSignalHistoryItem = {
  date: string
  direction: string
  catalyst: string
  return5d?: string
  note?: string
}

function normalizeSignalHistory(
  analysisSignalHistory?: SignalHistoryEntry[],
  fallbackRows: SignalHistoryRow[] = [],
): NormalizedSignalHistoryItem[] {
  if (analysisSignalHistory && analysisSignalHistory.length > 0) {
    return analysisSignalHistory.map((row) => ({
      date: row.date,
      direction: row.direction,
      catalyst: row.catalyst,
      return5d: row.return_5d,
      note: row.note,
    }))
  }

  return fallbackRows.map((row) => ({
    date: row.signal_date,
    direction: row.signal_direction,
    catalyst: row.catalyst_tag,
    return5d: row.return_5d,
    note: row.trade_frame_scenario,
  }))
}

function buildSectorComparisonRows(comparison?: SectorComparison): Array<{
  label: string
  company: string
  peerAverage: string
  difference?: string
}> {
  if (!comparison) {
    return []
  }

  const metricMap: Array<{ key: 'pe_ratio' | 'rs_vs_spy' | 'price_change_30d'; label: string }> = [
    { key: 'pe_ratio', label: 'P/E' },
    { key: 'rs_vs_spy', label: 'RS vs SPY' },
    { key: 'price_change_30d', label: '30D Return' },
  ]

  const rows: Array<{ label: string; company: string; peerAverage: string; difference?: string }> = []

  for (const { key, label } of metricMap) {
    const metric = comparison[key]
    if (!metric || (!metric.company && !metric.peer_average)) {
      continue
    }

    rows.push({
      label,
      company: metric.company ?? 'N/A',
      peerAverage: metric.peer_average ?? 'N/A',
      difference: metric.difference ?? metric.premium_discount,
    })
  }

  return rows
}

function getValuationScoreClass(score: string): string {
  const num = parseInt(score, 10)
  if (isNaN(num)) return ''
  if (num >= 8) return 'valuation-undervalued'
  if (num >= 5) return 'valuation-fair'
  return 'valuation-overvalued'
}

function getValuationLabel(score: string): string {
  const num = parseInt(score, 10)
  if (isNaN(num)) return ''
  if (num >= 8) return '저평가'
  if (num >= 5) return '적정'
  return '고평가'
}
