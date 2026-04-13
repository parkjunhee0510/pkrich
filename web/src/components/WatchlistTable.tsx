import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { TickerAnalysisData } from '../types'
import { parseNumericChange, changeColor, extractSignalDirection } from '../utils/format'
import { SignalBadge } from './SignalBadge'
import { SecFilingBadges } from './SecFilingBadges'
import { InfoTooltip } from './InfoTooltip'
import {
  buildPositioningGrid,
  buildPositionSizingSummary,
  buildPriceActionTags,
  computeSetupScore,
  extractActionPlan,
  getLatestCatalystItem,
  getNextEarningsEvent,
} from '../utils/trader'

type DensityMode = 'compact' | 'comfortable' | 'focus'

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

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const orderedTickers = isDndEnabled
    ? reorderByCustom(tickers, customOrder)
    : tickers

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event
      if (!over || active.id === over.id) return

      const currentIds = orderedTickers.map((t) => t.ticker)
      const oldIndex = currentIds.indexOf(active.id as string)
      const newIndex = currentIds.indexOf(over.id as string)
      if (oldIndex === -1 || newIndex === -1) return

      const newOrder = arrayMove(currentIds, oldIndex, newIndex)
      setCustomOrder(newOrder)
      saveCustomOrder(newOrder)
      if (!isDndEnabled) setIsDndEnabled(true)
    },
    [orderedTickers, isDndEnabled],
  )

  const handleResetOrder = () => {
    setCustomOrder([])
    saveCustomOrder([])
    setIsDndEnabled(false)
  }

  return (
    <div className="watchlist-list-wrapper">
      <div className="watchlist-dnd-toolbar">
        <label className="watchlist-dnd-toggle">
          <input
            type="checkbox"
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
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={orderedTickers.map((t) => t.ticker)} strategy={verticalListSortingStrategy}>
          <div className="watchlist-list" data-density={density}>
            {orderedTickers.map((ticker) => (
              <SortableWatchlistCard
                key={ticker.ticker}
                ticker={ticker}
                accountSize={accountSize}
                density={density}
                isDndEnabled={isDndEnabled}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  )
}

function SortableWatchlistCard({
  ticker,
  accountSize,
  density,
  isDndEnabled,
}: {
  ticker: TickerAnalysisData
  accountSize: number
  density: DensityMode
  isDndEnabled: boolean
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: ticker.ticker })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 10 : undefined,
  }

  const pct = parseNumericChange(ticker.data_snapshot['Daily Change'] ?? '0')
  const signalDirection = extractSignalDirection(ticker.signal_or_takeaway)
  const setup = computeSetupScore(ticker)
  const sizingSummary = buildPositionSizingSummary(ticker, accountSize)
  const actionPlan = extractActionPlan(ticker)
  const scoreFactorTags = setup.tags.slice(0, 2)
  const priceActionTags = buildPriceActionTags(ticker).slice(0, 3)
  const earningsEvent = getNextEarningsEvent(ticker)
  const latestCatalyst = getLatestCatalystItem(ticker)
  const positioningGrid = buildPositioningGrid(ticker)
  const contextSummary = buildContextSummary(ticker)

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={`watchlist-card ${getSetupToneClass(setup.score)}${isDragging ? ' dragging' : ''}`}
    >
      <div className="watchlist-card-head">
        <div className="watchlist-card-title-block">
          <div className="watchlist-card-title-row">
            {isDndEnabled && (
              <span className="watchlist-drag-handle" {...attributes} {...listeners} title="드래그하여 순서 변경">
                ⠿
              </span>
            )}
            <Link to={`/ticker/${ticker.ticker}`} className="ticker-link">
              {ticker.ticker}
            </Link>
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
        <div className="watchlist-card-score">
          <strong>{setup.score}</strong>
          <span>Setup Score</span>
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
      </div>

      <div className="watchlist-card-chip-row">
        {scoreFactorTags.map((tag) => (
          <span key={`score-${tag}`} className="setup-tag score-factor-chip">
            {tag}
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
            {earningsEvent.timing ? ` · ${earningsEvent.timing}` : ''}
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
  return `톤 확신도 ${levelMap[normalized]} (${percentage}%)`
}
