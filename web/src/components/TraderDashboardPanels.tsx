import { useState } from 'react'

const BEAT_MISS_LABELS: Record<string, string> = {
  beat: '상회',
  miss: '하회',
  'in-line': '부합',
  'N/A': '미확인',
}
import { Link } from 'react-router-dom'
import type { CatalystFeedSections, EarningsBoardSection, SetupScoreCard, SignalPerformanceHighlight } from '../utils/trader'
import type { TickerAnalysisData } from '../types'
import { SecFilingBadges } from './SecFilingBadges'
import { buildPriceActionTags, buildOptionsSignalTags, computeSetupScore, getUnusualActivityMeta, summarizeUnusualActivityShort } from '../utils/trader'
import { InfoTooltip } from './InfoTooltip'

export function TodaySetupBoard({ cards }: { cards: SetupScoreCard[] }) {
  if (cards.length === 0) {
    return (
      <section className="dashboard-panel-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>오늘의 셋업</h3>
            <p className="section-kicker">오늘 셋업 기준을 충족한 종목이 없습니다. 실적 보드나 하드 촉매 피드에서 다음 후보를 먼저 확인해보세요.</p>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="dashboard-panel-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>
            오늘의 셋업 <InfoTooltip content="D-day, hard catalyst, RVOL, RS, Forward vs TTM 등을 합쳐 오늘 먼저 볼 종목을 추립니다." />
          </h3>
          <p className="section-kicker">강한 촉매, 실적 일정, RVOL, 상대강도를 기준으로 오늘 먼저 볼 종목만 압축해서 보여줍니다.</p>
        </div>
      </div>
      <div className="setup-card-grid">
        {cards.map((card) => {
          const unusualMeta = getUnusualActivityMeta(card.rawOptionsUnusualActivity)
          const unusualSummary = summarizeUnusualActivityShort(card.rawOptionsUnusualActivity)

          return (
          <Link key={card.ticker} to={`/ticker/${card.ticker}`} className="setup-card">
            <div className="setup-card-head">
              <div className="setup-card-title-block">
                <strong>{card.ticker}</strong>
                <span>{card.name}</span>
              </div>
              <div className="setup-score-badge">
                <span>{card.focusLabel}</span>
                <strong>{card.score}</strong>
              </div>
            </div>
            <div className="setup-metric-row">
              <div className="setup-metric-cell">
                <span className="setup-metric-label">실적 일정</span>
                <strong className="setup-metric-value">{card.earningsDday}</strong>
              </div>
              <div className="setup-metric-cell">
                <span className="setup-metric-label">섹터 RS</span>
                <strong className="setup-metric-value">{card.sectorRs}</strong>
              </div>
              <div className="setup-metric-cell">
                <span className="setup-metric-label">Forward vs TTM</span>
                <strong className="setup-metric-value">{card.forwardVsTtm}</strong>
              </div>
              <div className="setup-metric-cell">
                <span className="setup-metric-label">최근 분기 결과</span>
                <strong className="setup-metric-value">{BEAT_MISS_LABELS[card.latestBeatMiss] ?? card.latestBeatMiss}</strong>
              </div>
              <div className="setup-metric-cell">
                <span className="setup-metric-label">EPS 성장률</span>
                <strong className="setup-metric-value">{card.epsGrowth}</strong>
              </div>
            </div>
            <div className="setup-action-stack">
              <span className="setup-direction">{card.actionPlan.direction}</span>
              <p>{card.actionPlan.thesis}</p>
              <p>진입존 {card.actionPlan.entry}</p>
              <p>무효화 {card.actionPlan.invalidation}</p>
              <p>다음 촉매 {card.actionPlan.nextCatalyst}</p>
              {unusualSummary ? (
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
                  <p className="setup-option-note">옵션: {unusualSummary}</p>
                </>
              ) : null}
            </div>
            <div className="setup-tag-row">
              {card.beatStreak > 0 && (
                <span className="setup-tag">
                  연속 상회 {card.beatStreak}분기
                </span>
              )}
              {card.optionTags.map((tag) => (
                <span
                  key={tag.label}
                  className={`setup-tag ${tag.tone ? `options-chip options-chip-${tag.tone}` : ''} ${tag.emphasis === 'alert' ? 'setup-tag-alert' : ''}`.trim()}
                >
                  {tag.label}
                </span>
              ))}
              {card.tags.map((tag) => (
                <span key={tag} className="setup-tag">
                  {tag}
                </span>
              ))}
            </div>
          </Link>
          )
        })}
      </div>
    </section>
  )
}

export function EarningsBoard({ sections }: { sections: EarningsBoardSection[] }) {
  const visibleSections = sections.filter((section) => section.items.length > 0)
  if (visibleSections.length === 0) {
    return (
      <section className="dashboard-panel-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>실적 발표</h3>
            <p className="section-kicker">가까운 실적 이벤트가 없습니다. 점수순 카드나 하드 촉매 피드로 이동해 다음 일정이 있는 종목부터 확인해보세요.</p>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="dashboard-panel-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>
            실적 플레이 보드 <InfoTooltip content="오늘, D-3, D-7, D-21 구간으로 나눠 BMO/AMC와 최근 beat-miss를 빠르게 확인합니다." />
          </h3>
          <p className="section-kicker">D-21 이내 실적 종목만 따로 묶어 BMO/AMC, beat-miss, Forward vs TTM을 한 번에 확인합니다.</p>
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
                    <span className="setup-tag">{BEAT_MISS_LABELS[item.beatMiss] ?? item.beatMiss}</span>
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
  const ordered: Array<{ key: keyof CatalystFeedSections; label: string; description: string }> = [
    { key: 'hard', label: 'Hard Catalyst', description: '지금 바로 체크할 강한 촉매' },
    { key: 'medium', label: 'Medium Catalyst', description: '중요하지만 한 단계 더 확인할 촉매' },
    { key: 'soft', label: 'Soft Catalyst', description: '참고용으로 따라갈 수 있는 촉매' },
  ]

  const totalItems = ordered.reduce((sum, item) => sum + sections[item.key].length, 0)
  const firstAvailable = ordered.find(({ key }) => sections[key].length > 0)?.key ?? 'hard'
  const [selectedLevel, setSelectedLevel] = useState<keyof CatalystFeedSections>(firstAvailable)
  const activeLevel = sections[selectedLevel].length > 0 ? selectedLevel : firstAvailable
  const activeMeta = ordered.find(({ key }) => key === activeLevel) ?? ordered[0]
  const activeItems = sections[activeLevel]

  return (
    <section className="dashboard-panel-section catalyst-feed-panel">
      <div className="section-header-with-kicker">
        <div>
          <h3>
            Catalyst Feed <InfoTooltip content="뉴스와 공시를 hard, medium, soft 촉매로 나눠 지금 먼저 볼 강도부터 정렬합니다." />
          </h3>
          <p className="section-kicker">뉴스와 공시를 촉매 강도별로 분리해서 지금 더 중요한 것부터 먼저 읽히게 정리합니다.</p>
        </div>
      </div>

      <div className="catalyst-tab-row">
        {ordered.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            className={`catalyst-tab ${activeLevel === key ? 'active' : ''}`}
            onClick={() => setSelectedLevel(key)}
          >
            <span>{label}</span>
            <strong>{sections[key].length}</strong>
          </button>
        ))}
      </div>

      <div className={`catalyst-feed-column catalyst-${activeLevel}`}>
        <div className="catalyst-feed-head">
          <div className="catalyst-feed-head-copy">
            <strong>{activeMeta.label}</strong>
            <span>{activeMeta.description}</span>
          </div>
          <span>{activeItems.length}개</span>
        </div>
        {activeItems.length > 0 ? (
          <ul className="catalyst-feed-list catalyst-feed-scroll">
            {activeItems.map((item) => (
              <li key={`${item.ticker}-${item.title}`} className="catalyst-feed-item">
                <div className="catalyst-feed-title-row">
                  <Link to={`/ticker/${item.ticker}`} className="ticker-link">
                    {item.ticker}
                  </Link>
                  <span className="filing-form-chip">{item.tag}</span>
                </div>
                <a href={item.link} target="_blank" rel="noopener noreferrer" className="catalyst-feed-link">
                  {item.title}
                </a>
                <div className="news-meta">{item.source} · {item.publishedAt}</div>
                <p className="price-action-subtext">{item.note}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty">
            {totalItems === 0
              ? '오늘은 표시할 촉매가 없습니다. 대신 실적 플레이 보드나 점수순 카드부터 확인해보세요.'
              : activeLevel === 'hard'
                ? '현재 hard 촉매는 비어 있습니다. medium 탭으로 내려가면 오늘 이어서 볼 만한 재료를 더 찾을 수 있습니다.'
                : activeLevel === 'medium'
                  ? '현재 medium 촉매는 비어 있습니다. soft 탭이나 실적 플레이 보드에서 다음 후보를 이어서 확인해보세요.'
                  : '현재 soft 촉매도 비어 있습니다. 실적 플레이 보드나 오늘의 셋업으로 돌아가 우선순위를 다시 잡아보세요.'}
          </p>
        )}
      </div>
    </section>
  )
}

export function SignalPerformanceBoard({ highlights }: { highlights: SignalPerformanceHighlight[] }) {
  if (highlights.length === 0) {
    return (
      <section className="dashboard-panel-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>시그널 검증 랭킹</h3>
            <p className="section-kicker">아직 누적된 검증 표본이 충분하지 않습니다. 신호가 더 쌓이면 방향별 승률과 평균 수익률이 자동으로 요약됩니다.</p>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="dashboard-panel-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>
            시그널 검증 랭킹 <InfoTooltip content="bull/bear 승률, hard catalyst 1D 평균, beat setup 5D 평균처럼 최근 검증 결과를 빠르게 훑습니다." />
          </h3>
          <p className="section-kicker">bull/bear 승률과 hard catalyst, beat setup의 최근 검증 결과를 빠르게 점검합니다.</p>
        </div>
      </div>
      <div className="signal-highlight-grid compact">
        {highlights.map((highlight) => (
          <div key={highlight.label} className="signal-highlight-card compact">
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
  const optionsTags = buildOptionsSignalTags(ticker)

  return (
    <>
      <div>{ticker.name}</div>
      <div className="watchlist-meta-row">
        <span className="setup-score-inline">{setup.score}</span>
        <span className="watchlist-focus-label">{setup.focusLabel}</span>
      </div>
      <SecFilingBadges tags={ticker.sec_filing_tags} />
      {(priceActionTags.length > 0 || optionsTags.length > 0) && (
        <div className="watchlist-chip-row">
          {optionsTags.map((tag) => (
            <span
              key={tag.label}
              className={`setup-tag ${tag.tone ? `options-chip options-chip-${tag.tone}` : ''} ${tag.emphasis === 'alert' ? 'setup-tag-alert' : ''}`.trim()}
            >
              {tag.label}
            </span>
          ))}
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

