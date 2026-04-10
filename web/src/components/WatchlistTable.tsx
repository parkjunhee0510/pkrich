import { Link } from 'react-router-dom'
import type { TickerAnalysisData } from '../types'
import { parseNumericChange, changeColor } from '../utils/format'
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

export function WatchlistTable({
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
      {tickers.map((ticker) => {
        const pct = parseNumericChange(ticker.data_snapshot['Daily Change'] ?? '0')
        const setup = computeSetupScore(ticker)
        const sizingSummary = buildPositionSizingSummary(ticker, accountSize)
        const actionPlan = extractActionPlan(ticker)
        const scoreFactorTags = setup.tags.slice(0, 2)
        const priceActionTags = buildPriceActionTags(ticker).slice(0, 3)
        const earningsEvent = getNextEarningsEvent(ticker)
        const latestCatalyst = getLatestCatalystItem(ticker)
        const positioningGrid = buildPositioningGrid(ticker)

        return (
          <article key={ticker.ticker} className={`watchlist-card ${getSetupToneClass(setup.score)}`}>
            <div className="watchlist-card-head">
              <div className="watchlist-card-title-block">
                <div className="watchlist-card-title-row">
                  <Link to={`/ticker/${ticker.ticker}`} className="ticker-link">
                    {ticker.ticker}
                  </Link>
                  <SignalBadge changePercent={pct} />
                  <span className="watchlist-focus-pill">{setup.focusLabel}</span>
                  {latestCatalyst && (
                    <span className={`watchlist-catalyst-pill ${latestCatalyst.level}`}>
                      {formatCatalystLevel(latestCatalyst.level)}
                    </span>
                  )}
                </div>
                <div className="watchlist-card-name">{ticker.name}</div>
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
      })}
    </div>
  )
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
