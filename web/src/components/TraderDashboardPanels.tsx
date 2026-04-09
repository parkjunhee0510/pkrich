import { Link } from 'react-router-dom'
import type { CatalystFeedSections, EarningsBoardSection, SetupScoreCard, SignalPerformanceHighlight } from '../utils/trader'
import type { TickerAnalysisData } from '../types'
import { SecFilingBadges } from './SecFilingBadges'
import { buildPriceActionTags, computeSetupScore } from '../utils/trader'

export function TodaySetupBoard({ cards }: { cards: SetupScoreCard[] }) {
  if (cards.length === 0) {
    return null
  }

  return (
    <section className="dashboard-panel-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>오늘의 셋업</h3>
          <p className="section-kicker">하드 촉매, 실적 일정, RVOL, 상대강도 기준으로 오늘 가장 먼저 볼 종목</p>
        </div>
      </div>
      <div className="setup-card-grid">
        {cards.map((card) => (
          <Link key={card.ticker} to={`/ticker/${card.ticker}`} className="setup-card">
            <div className="setup-card-head">
              <div>
                <strong>{card.ticker}</strong>
                <span>{card.name}</span>
              </div>
              <div className="setup-score-badge">
                <span>{card.focusLabel}</span>
                <strong>{card.score}</strong>
              </div>
            </div>
            <div className="setup-metric-row">
              <span>{card.earningsDday}</span>
              <span>{card.forwardVsTtm}</span>
              <span>{card.latestBeatMiss}</span>
              <span>{card.epsGrowth}</span>
            </div>
            <div className="setup-action-stack">
              <span className="setup-direction">{card.actionPlan.direction}</span>
              <p>{card.actionPlan.thesis}</p>
              <p>진입존 {card.actionPlan.entry}</p>
              <p>무효화 {card.actionPlan.invalidation}</p>
              <p>다음 촉매 {card.actionPlan.nextCatalyst}</p>
            </div>
            <div className="setup-tag-row">
              {card.tags.map((tag) => (
                <span key={tag} className="setup-tag">
                  {tag}
                </span>
              ))}
            </div>
          </Link>
        ))}
      </div>
    </section>
  )
}

export function EarningsBoard({ sections }: { sections: EarningsBoardSection[] }) {
  const visibleSections = sections.filter((section) => section.items.length > 0)
  if (visibleSections.length === 0) {
    return null
  }

  return (
    <section className="dashboard-panel-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>실적 플레이 보드</h3>
          <p className="section-kicker">D-21 안쪽 실적 종목만 분리해서 BMO/AMC, beat/miss, Forward vs TTM까지 한 번에 확인</p>
        </div>
      </div>
      <div className="earnings-board-grid">
        {visibleSections.map((section) => (
          <div key={section.key} className="earnings-board-column">
            <div className="earnings-board-head">
              <strong>{section.label}</strong>
              <span>{section.items.length}개</span>
            </div>
            <div className="earnings-board-list">
              {section.items.map((item) => (
                <Link key={`${item.ticker}-${item.date}`} to={`/ticker/${item.ticker}`} className="earnings-board-card">
                  <div className="earnings-board-row">
                    <strong>{item.ticker}</strong>
                    <span>{item.dayLabel}{item.timing ? ` · ${item.timing}` : ''}</span>
                  </div>
                  <div className="earnings-board-row muted">
                    <span>{item.name}</span>
                    <span>{item.date}</span>
                  </div>
                  <div className="earnings-board-chip-row">
                    <span className="setup-tag">{item.beatMiss}</span>
                    <span className="setup-tag">{item.forwardVsTtm}</span>
                    <span className="setup-tag">{item.surprise}</span>
                    <span className="setup-tag">{item.signal}</span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

export function CatalystFeed({ sections }: { sections: CatalystFeedSections }) {
  const ordered: Array<{ key: keyof CatalystFeedSections; label: string }> = [
    { key: 'hard', label: 'Hard Catalyst' },
    { key: 'medium', label: 'Medium Catalyst' },
    { key: 'soft', label: 'Soft Catalyst' },
  ]

  if (ordered.every(({ key }) => sections[key].length === 0)) {
    return null
  }

  return (
    <section className="dashboard-panel-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>Catalyst Feed</h3>
          <p className="section-kicker">뉴스와 공시를 촉매 강도별로 분리해서, 지금 왜 중요한지부터 먼저 읽히게 정리</p>
        </div>
      </div>
      <div className="catalyst-feed-grid">
        {ordered.map(({ key, label }) => (
          <div key={key} className={`catalyst-feed-column catalyst-${key}`}>
            <div className="catalyst-feed-head">
              <strong>{label}</strong>
              <span>{sections[key].length}개</span>
            </div>
            {sections[key].length > 0 ? (
              <ul className="catalyst-feed-list">
                {sections[key].map((item) => (
                  <li key={`${item.ticker}-${item.title}`} className="catalyst-feed-item">
                    <div className="catalyst-feed-title-row">
                      <Link to={`/ticker/${item.ticker}`} className="ticker-link">
                        {item.ticker}
                      </Link>
                      <span className="filing-form-chip">{item.tag}</span>
                    </div>
                    <a href={item.link} target="_blank" rel="noopener noreferrer">
                      {item.title}
                    </a>
                    <div className="news-meta">{item.source} · {item.publishedAt}</div>
                    <p className="price-action-subtext">{item.note}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty">표시할 촉매가 없습니다.</p>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

export function SignalPerformanceBoard({ highlights }: { highlights: SignalPerformanceHighlight[] }) {
  if (highlights.length === 0) {
    return null
  }

  return (
    <section className="dashboard-panel-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>시그널 검증 랭킹</h3>
          <p className="section-kicker">bull/bear 승률과 하드 촉매, beat setup의 최근 성과를 빠르게 점검</p>
        </div>
      </div>
      <div className="signal-highlight-grid">
        {highlights.map((highlight) => (
          <div key={highlight.label} className="signal-highlight-card">
            <span className="price-action-label">{highlight.label}</span>
            <strong>{highlight.value}</strong>
            <span className="price-action-subtext">{highlight.note}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

export function TickerMetaStack({ ticker }: { ticker: TickerAnalysisData }) {
  const setup = computeSetupScore(ticker)
  const priceActionTags = buildPriceActionTags(ticker)

  return (
    <>
      <div>{ticker.name}</div>
      <div className="watchlist-meta-row">
        <span className="setup-score-inline">{setup.score}</span>
        <span className="watchlist-focus-label">{setup.focusLabel}</span>
      </div>
      <SecFilingBadges tags={ticker.sec_filing_tags} />
      {priceActionTags.length > 0 && (
        <div className="watchlist-chip-row">
          {priceActionTags.map((tag) => (
            <span key={tag} className="setup-tag">
              {tag}
            </span>
          ))}
        </div>
      )}
      {ticker.upcoming_events.length > 0 && (
        <div className="event-badges">
          {ticker.upcoming_events.slice(0, 2).map((event) => (
            <span key={`${event.type}-${event.date}`} className="event-badge">
              {event.label} D-{event.days_until}{event.timing ? ` · ${event.timing}` : ''}
            </span>
          ))}
        </div>
      )}
    </>
  )
}
