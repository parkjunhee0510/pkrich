import {
  Suspense,
  lazy,
  useState,
  type CSSProperties,
  type HTMLAttributes,
  type KeyboardEvent,
  type MouseEvent,
  type Ref,
} from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { TickerAnalysisData } from '../types'
import { parseNumericChange, changeColor, extractSignalDirection } from '../utils/format'
import { SignalBadge } from './SignalBadge'
import { SecFilingBadges } from './SecFilingBadges'
import { InfoTooltip } from './InfoTooltip'
import { CommitteeSummaryStrip } from './CommitteeSummaryStrip'
import {
  buildOptionsSignalTags,
  buildPositioningGrid,
  buildPositionSizingSummary,
  buildPriceActionTags,
  computeSetupScore,
  extractActionPlan,
  getLatestCatalystItem,
  getNextEarningsEvent,
  getUnusualActivityMeta,
  summarizeUnusualActivityShort,
} from '../utils/trader'

const WatchlistDndList = lazy(() =>
  import('./WatchlistDndList').then((module) => ({ default: module.WatchlistDndList })),
)

export type DensityMode = 'compact' | 'comfortable' | 'focus'
type DragHandleProps = HTMLAttributes<HTMLSpanElement>
type DropTargetProps = Pick<HTMLAttributes<HTMLElement>, 'onDragOver' | 'onDrop'>

const DECISION_LABEL: Record<string, string> = {
  buy: '매수',
  watch: '관찰',
  avoid: '회피',
}

const STORAGE_KEY = 'pkrich-watchlist-order'

function loadCustomOrder(): string[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : []
  } catch {
    return []
  }
}

function saveCustomOrder(order: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(order))
  } catch {
    // ignore
  }
}

export function WatchlistTable({
  tickers,
  accountSize,
  density,
}: {
  tickers: TickerAnalysisData[]
  accountSize: number
  density: DensityMode
}) {
  const [customOrder, setCustomOrder] = useState<string[]>(() => loadCustomOrder())
  const [isDndEnabled, setIsDndEnabled] = useState(customOrder.length > 0)

  const orderedTickers = isDndEnabled
    ? reorderByCustom(tickers, customOrder)
    : tickers

  const handleResetOrder = () => {
    setCustomOrder([])
    saveCustomOrder([])
    setIsDndEnabled(false)
  }

  const handleOrderChange = (newOrder: string[]) => {
    setCustomOrder(newOrder)
    saveCustomOrder(newOrder)
  }

  return (
    <div className="watchlist-list-wrapper cozy-premium-watchlist">
      <div className="watchlist-dnd-toolbar">
        <label className="watchlist-dnd-toggle">
          <input
            type="checkbox"
            aria-label="워치리스트 커스텀 정렬 사용"
            checked={isDndEnabled}
            onChange={(e) => {
              setIsDndEnabled(e.target.checked)
              if (!e.target.checked) handleResetOrder()
            }}
          />
          <span>커스텀 정렬</span>
        </label>
        {isDndEnabled && customOrder.length > 0 && (
          <button type="button" className="watchlist-dnd-reset" onClick={handleResetOrder}>
            정렬 초기화
          </button>
        )}
      </div>
      {isDndEnabled ? (
        <Suspense fallback={<WatchlistStaticList tickers={orderedTickers} accountSize={accountSize} density={density} />}>
          <WatchlistDndList
            tickers={orderedTickers}
            accountSize={accountSize}
            density={density}
            onOrderChange={handleOrderChange}
          />
        </Suspense>
      ) : (
        <WatchlistStaticList tickers={tickers} accountSize={accountSize} density={density} />
      )}
    </div>
  )
}

function WatchlistStaticList({
  tickers,
  accountSize,
  density,
}: {
  tickers: TickerAnalysisData[]
  accountSize: number
  density: DensityMode
}) {
  return (
    <div className="watchlist-list" data-density={density}>
      {tickers.map((ticker) => (
        <WatchlistCard
          key={ticker.ticker}
          ticker={ticker}
          accountSize={accountSize}
          density={density}
          isDndEnabled={false}
        />
      ))}
    </div>
  )
}

export function WatchlistCard({
  ticker,
  accountSize,
  density,
  isDndEnabled,
  cardRef,
  dragStyle,
  dragHandleProps,
  dropTargetProps,
  isDragging = false,
}: {
  ticker: TickerAnalysisData
  accountSize: number
  density: DensityMode
  isDndEnabled: boolean
  cardRef?: Ref<HTMLElement>
  dragStyle?: CSSProperties
  dragHandleProps?: DragHandleProps
  dropTargetProps?: DropTargetProps
  isDragging?: boolean
}) {
  const navigate = useNavigate()
  const pct = parseNumericChange(ticker.data_snapshot['Daily Change'] ?? '0')
  const signalDirection = extractSignalDirection(ticker.signal_or_takeaway)
  const setup = computeSetupScore(ticker)
  const convictionScore = ticker.decision?.conviction
  const displayScore = typeof convictionScore === 'number' ? convictionScore : setup.score
  const scoreSource: 'conviction' | 'setup' = typeof convictionScore === 'number' ? 'conviction' : 'setup'
  const sizingSummary = buildPositionSizingSummary(ticker, accountSize)
  const actionPlan = extractActionPlan(ticker)
  const scoreFactorTags = setup.tags.slice(0, 2)
  const priceActionTags = buildPriceActionTags(ticker).slice(0, 3)
  const earningsEvent = getNextEarningsEvent(ticker)
  const latestCatalyst = getLatestCatalystItem(ticker)
  const positioningGrid = buildPositioningGrid(ticker)
  const optionTags = buildOptionsSignalTags(ticker)
  const unusualActivitySummary = summarizeUnusualActivityShort(ticker.options_summary?.unusual_activity)
  const unusualMeta = getUnusualActivityMeta(ticker.options_summary?.unusual_activity)
  const contextSummary = buildContextSummary(ticker)
  const dragHandleTitle = dragHandleProps?.title ?? 'Drag to reorder'

  function navigateToTicker() {
    navigate(`/ticker/${ticker.ticker}`)
  }

  function handleCardClick(e: MouseEvent<HTMLElement>) {
    if (isDragging) return
    const target = e.target as HTMLElement
    if (target.closest('a, button, [role="button"]')) return
    navigateToTicker()
  }

  function handleCardKeyDown(e: KeyboardEvent<HTMLElement>) {
    if (isDragging) return
    const target = e.target as HTMLElement
    if (target.closest('a, button, [role="button"]')) return
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      navigateToTicker()
    }
  }

  return (
    <article
      ref={cardRef}
      style={{ ...dragStyle, cursor: 'pointer' }}
      className={`watchlist-card ${getSetupToneClass(displayScore)}${isDragging ? ' dragging' : ''}`}
      role="link"
      tabIndex={0}
      aria-label={`${ticker.ticker} 상세 페이지 열기`}
      onClick={handleCardClick}
      onKeyDown={handleCardKeyDown}
      onDragOver={dropTargetProps?.onDragOver}
      onDrop={dropTargetProps?.onDrop}
    >
      <div className="watchlist-card-head">
        <div className="watchlist-card-title-block">
          <div className="watchlist-card-title-row">
            {isDndEnabled && (
              <span className="watchlist-drag-handle" {...dragHandleProps} title={dragHandleTitle}>
                ⠿
              </span>
            )}
            <Link to={`/ticker/${ticker.ticker}`} className="ticker-link">
              {ticker.ticker}
            </Link>
            {ticker.decision && (
              <span className={`watchlist-decision-pill decision-pill-${ticker.decision.action}`}>
                {DECISION_LABEL[ticker.decision.action] ?? ticker.decision.action}
              </span>
            )}
            <SignalBadge changePercent={pct} signalDirection={signalDirection} />
            <span className="watchlist-focus-pill">{setup.focusLabel}</span>
            {latestCatalyst && (
              <span className={`watchlist-catalyst-pill ${latestCatalyst.level}`}>
                {formatCatalystLevel(latestCatalyst.level)}
              </span>
            )}
          </div>
          <div className="watchlist-card-name">{ticker.name}</div>
          {density !== 'compact' && contextSummary ? (
            <div className="watchlist-card-context">{contextSummary}</div>
          ) : null}
        </div>
        <div className="watchlist-card-score" title={scoreSource === 'conviction' ? '파이프라인 의사결정 컨빅션 (src/decision/)' : '실시간 셋업 휴리스틱 (decision 없음)'}>
          <strong>{displayScore}</strong>
          <span>{scoreSource === 'conviction' ? 'Conviction' : 'Setup Score'}</span>
        </div>
      </div>

      <div className="watchlist-stat-grid">
        <div className={`watchlist-stat-card ${getPriceToneClass(ticker)}`}>
          <span className="watchlist-stat-label">
            Price
            <InfoTooltip content="현재가가 SMA50/SMA200 위에 있는지에 따라 추세 우위 여부를 빠르게 읽는 카드입니다." />
          </span>
          <strong>{ticker.data_snapshot['Price']}</strong>
        </div>
        <div className={`watchlist-stat-card ${getChangeToneClass(pct)}`}>
          <span className="watchlist-stat-label">
            Change
            <InfoTooltip content="당일 등락 강도입니다. 큰 변동일수록 이벤트 민감도가 높을 수 있습니다." />
          </span>
          <strong style={{ color: changeColor(pct) }}>{ticker.data_snapshot['Daily Change']}</strong>
        </div>
        <div className={`watchlist-stat-card ${getMomentumToneClass(ticker)}`}>
          <span className="watchlist-stat-label">
            7D / 30D
            <InfoTooltip content="단기와 중기 수익률을 함께 보여줘 모멘텀 지속 여부를 확인합니다." />
          </span>
          <strong>{ticker.period_changes?.['7d'] ?? 'N/A'}</strong>
          <span className="watchlist-stat-sub">{ticker.period_changes?.['30d'] ?? 'N/A'}</span>
        </div>
        <div className={`watchlist-stat-card ${getEarningsToneClass(earningsEvent)}`}>
          <span className="watchlist-stat-label">
            Next Earnings
            <InfoTooltip content="실적일이 가까울수록 카드 톤이 강해집니다. BMO/AMC도 함께 표시됩니다." />
          </span>
          <strong>{earningsEvent ? `D-${earningsEvent.days_until}` : 'N/A'}</strong>
          <span className="watchlist-stat-sub">
            {earningsEvent
              ? `${earningsEvent.date}${earningsEvent.timing ? ` · ${earningsEvent.timing}` : ''}`
              : 'No scheduled earnings'}
          </span>
        </div>
      
        <div className={`watchlist-stat-card ${getSectorRsToneClass(ticker)}`}>
          <span className="watchlist-stat-label">
            Sector RS
            <InfoTooltip content="Performance relative to the mapped sector ETF. Positive means stronger than the sector benchmark, negative means weaker than peers." />
          </span>
          <strong>{ticker.price_action?.rs_vs_sector_etf ?? 'N/A'}</strong>
          <span className="watchlist-stat-sub">vs mapped sector ETF</span>
        </div>
      </div>

      <div className="watchlist-card-chip-row">
        {ticker.analysis_consensus?.selection_reason === 'cap_exceeded' && (
          <span className="setup-tag setup-tag-alert" title="일일 앙상블 상한에 걸려 2차 deep 재분석 대상에서 제외됐습니다.">
            앙상블 보류
          </span>
        )}
        {scoreFactorTags.map((tag) => (
          <span key={`score-${tag}`} className="setup-tag score-factor-chip">
            {tag}
          </span>
        ))}
        {optionTags.map((tag) => (
          <span
            key={tag.label}
            className={`setup-tag ${tag.tone ? `options-chip options-chip-${tag.tone}` : ''} ${tag.emphasis === 'alert' ? 'setup-tag-alert' : ''}`.trim()}
          >
            {tag.label}
          </span>
        ))}
        {ticker.sec_filing_tags.length > 0 && <SecFilingBadges tags={ticker.sec_filing_tags.slice(0, 2)} />}
        {priceActionTags.map((tag) => (
          <span key={tag} className="setup-tag">
            {tag}
          </span>
        ))}
        {earningsEvent && (
          <span className="event-badge">
            {earningsEvent.label} D-{earningsEvent.days_until}
            {earningsEvent.timing ? ` ? ${earningsEvent.timing}` : ''}
          </span>
        )}
      </div>

      <div className="watchlist-detail-grid">
        <section className="watchlist-detail-card action">
          <span className="price-action-label">Action</span>
          <details className="watchlist-action-details">
            <summary>
              <strong>{actionPlan.direction}</strong>
              <span>{buildActionSummary(actionPlan, latestCatalyst, earningsEvent)}</span>
            </summary>
            <div className="watchlist-action-expanded">
              {unusualActivitySummary ? (
                <>
                  <div className="options-context-badges">
                    <span className={`options-context-badge posture-${unusualMeta?.postureTone ?? 'mixed'}`}>
                      {unusualMeta?.postureLabel ?? '변동성 대응'}
                    </span>
                    {unusualMeta?.strengthLabel ? (
                      <span className={`options-context-badge strength-${unusualMeta.strengthTone}`}>
                        {unusualMeta.strengthLabel}
                      </span>
                    ) : null}
                  </div>
                  <p className="watchlist-option-note">옵션: {unusualActivitySummary}</p>
                </>
              ) : null}
              <p>{actionPlan.thesis}</p>
              <p>진입존 {actionPlan.entry}</p>
              <p>무효화 {actionPlan.invalidation}</p>
              <p>다음 촉매 {actionPlan.nextCatalyst}</p>
            </div>
          </details>
        </section>

        <section className="watchlist-detail-card">
          <div className="watchlist-detail-head">
            <span className="price-action-label">Positioning</span>
            <InfoTooltip content="공매도, 애널리스트, 기관 보유, 옵션 IV를 2x2로 빠르게 읽는 포지셔닝 요약입니다." />
          </div>
          <div className="watchlist-positioning-grid">
            {positioningGrid.map((item) => (
              <div key={item.label} className="watchlist-positioning-cell">
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <small>{item.note}</small>
              </div>
            ))}
          </div>
        </section>

        <section className="watchlist-detail-card">
          <span className="price-action-label">Sizing</span>
          <strong>{sizingSummary.stopPrice}</strong>
          <p>{sizingSummary.positionShares}</p>
          <p>{sizingSummary.riskReward}</p>
        </section>
      </div>

      <CommitteeSummaryStrip committee={ticker.committee_analysis} />
    </article>
  )
}

function reorderByCustom(tickers: TickerAnalysisData[], order: string[]): TickerAnalysisData[] {
  if (order.length === 0) return tickers
  const tickerMap = new Map(tickers.map((t) => [t.ticker, t]))
  const ordered: TickerAnalysisData[] = []
  for (const sym of order) {
    const t = tickerMap.get(sym)
    if (t) {
      ordered.push(t)
      tickerMap.delete(sym)
    }
  }
  // append any new tickers not in the custom order
  for (const t of tickerMap.values()) {
    ordered.push(t)
  }
  return ordered
}

function formatCatalystLevel(level: 'hard' | 'medium' | 'soft'): string {
  if (level === 'hard') return 'Hard Catalyst'
  if (level === 'medium') return 'Medium Catalyst'
  return 'Soft Catalyst'
}

function getSetupToneClass(score: number): string {
  if (score >= 80) return 'setup-tone-high'
  if (score >= 65) return 'setup-tone-medium'
  if (score >= 50) return 'setup-tone-light'
  return 'setup-tone-muted'
}

function buildActionSummary(
  actionPlan: ReturnType<typeof extractActionPlan>,
  latestCatalyst: ReturnType<typeof getLatestCatalystItem>,
  earningsEvent: ReturnType<typeof getNextEarningsEvent>,
): string {
  const catalystLabel = summarizeCatalyst(earningsEvent, latestCatalyst, actionPlan.nextCatalyst)
  const entryLabel = `진입 ${shortenEntry(actionPlan.entry)}`
  return [catalystLabel, entryLabel].filter(Boolean).join(' · ')
}

function shortenEntry(entry: string): string {
  if (!entry) return '확인 필요'
  return entry.length > 22 ? `${entry.slice(0, 22)}...` : entry
}

function summarizeCatalyst(
  earningsEvent: ReturnType<typeof getNextEarningsEvent>,
  latestCatalyst: ReturnType<typeof getLatestCatalystItem>,
  fallbackText: string,
): string {
  if (earningsEvent) {
    return `실적 D-${earningsEvent.days_until}${earningsEvent.timing ? ` ${earningsEvent.timing}` : ''}`
  }
  if (latestCatalyst) {
    return `${formatCatalystLevel(latestCatalyst.level)} / ${latestCatalyst.tag}`
  }
  if (!fallbackText) {
    return '다음 촉매 대기'
  }
  return fallbackText.length > 28 ? `${fallbackText.slice(0, 28)}...` : fallbackText
}

function getPriceToneClass(ticker: TickerAnalysisData): string {
  const vsSma50 = parseSignedNumber(ticker.price_action?.price_vs_sma50)
  const vsSma200 = parseSignedNumber(ticker.price_action?.price_vs_sma200)
  if (vsSma50 !== null && vsSma200 !== null && vsSma50 >= 0 && vsSma200 >= 0) {
    return 'stat-tone-positive'
  }
  if (vsSma50 !== null && vsSma200 !== null && vsSma50 < 0 && vsSma200 < 0) {
    return 'stat-tone-negative'
  }
  return 'stat-tone-neutral'
}

function getChangeToneClass(changePercent: number): string {
  if (changePercent >= 1.5) return 'stat-tone-positive'
  if (changePercent <= -1.5) return 'stat-tone-negative'
  return 'stat-tone-neutral'
}

function getMomentumToneClass(ticker: TickerAnalysisData): string {
  const change7d = parseSignedNumber(ticker.period_changes?.['7d'])
  const change30d = parseSignedNumber(ticker.period_changes?.['30d'])
  if (change7d !== null && change30d !== null && change7d > 0 && change30d > 0) {
    return 'stat-tone-positive'
  }
  if (change7d !== null && change30d !== null && change7d < 0 && change30d < 0) {
    return 'stat-tone-negative'
  }
  return 'stat-tone-neutral'
}

function getEarningsToneClass(earningsEvent: ReturnType<typeof getNextEarningsEvent>): string {
  if (!earningsEvent) return 'stat-tone-neutral'
  const days = Number.parseInt(earningsEvent.days_until, 10)
  if (Number.isNaN(days)) return 'stat-tone-neutral'
  if (days <= 3) return 'stat-tone-negative'
  if (days <= 10) return 'stat-tone-caution'
  return 'stat-tone-positive'
}

function getSectorRsToneClass(ticker: TickerAnalysisData): string {
  const sectorRs = parseSignedNumber(ticker.price_action?.rs_vs_sector_etf)
  if (sectorRs === null) return 'stat-tone-neutral'
  if (sectorRs >= 2) return 'stat-tone-positive'
  if (sectorRs <= -2) return 'stat-tone-negative'
  return 'stat-tone-caution'
}

function parseSignedNumber(value?: string): number | null {
  if (!value) return null
  const match = value.replace(/,/g, '').match(/[-+]?\d*\.?\d+/)
  if (!match) return null
  const parsed = Number.parseFloat(match[0])
  return Number.isNaN(parsed) ? null : parsed
}

function buildContextSummary(ticker: TickerAnalysisData): string {
  const parts: string[] = []

  if (typeof ticker.news_tone?.confidence === 'number') {
    parts.push(formatNewsToneConfidence(ticker.news_tone.confidence))
  }

  if (ticker.sector_comparison?.summary) {
    parts.push(ticker.sector_comparison.summary)
  }

  return parts.join(' · ')
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
