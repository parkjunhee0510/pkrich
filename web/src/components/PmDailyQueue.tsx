import { Link } from 'react-router-dom'
import type { PMEventExposureItem, PMPriorityQueueItem, PMSwapCandidate, PMViewData } from '../types'

type PmDailyQueueProps = {
  pmView?: PMViewData | null
}

const DEFAULT_EMPTY_STATES = {
  swap_candidates: 'No swap review candidates today. Current holdings remain relatively stable on conviction and event calendar.',
  event_exposure_items: 'No urgent event exposure reviews today.',
  today_priority_queue: 'No priority review queue today. Portfolio review can stay with the standard dashboard sections below.',
} as const

export function PmDailyQueue({ pmView }: PmDailyQueueProps) {
  const swapCandidates = pmView?.swap_candidates ?? []
  const eventExposureItems = pmView?.event_exposure_items ?? []
  const todayPriorityQueue = pmView?.today_priority_queue ?? []
  const emptyStates = {
    swap_candidates: pmView?.empty_states?.swap_candidates || DEFAULT_EMPTY_STATES.swap_candidates,
    event_exposure_items: pmView?.empty_states?.event_exposure_items || DEFAULT_EMPTY_STATES.event_exposure_items,
    today_priority_queue: pmView?.empty_states?.today_priority_queue || DEFAULT_EMPTY_STATES.today_priority_queue,
  }

  return (
    <section className="dashboard-priority-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>PM Daily Queue</h3>
          <p className="section-kicker">
            포트폴리오 실행 지시가 아니라 오늘 먼저 검토할 항목을 빠르게 훑는 PM 검토 큐입니다.
            {pmView?.as_of ? ` 기준 시각 ${pmView.as_of}` : ''}
          </p>
        </div>
      </div>

      <div className="dashboard-priority-grid">
        <SwapReviewCard items={swapCandidates} emptyMessage={emptyStates.swap_candidates} />
        <EventExposureCard items={eventExposureItems} emptyMessage={emptyStates.event_exposure_items} />
        <TodayPriorityQueueCard items={todayPriorityQueue} emptyMessage={emptyStates.today_priority_queue} />
      </div>
    </section>
  )
}

function SwapReviewCard({
  items,
  emptyMessage,
}: {
  items: PMSwapCandidate[]
  emptyMessage: string
}) {
  return (
    <article className="dashboard-priority-card">
      <div className="dashboard-priority-head">
        <span className="dashboard-priority-kicker">{items.length > 0 ? `TOP ${Math.min(items.length, 5)}` : 'Stable'}</span>
        <strong>Swap Review Candidates</strong>
      </div>

      {items.length > 0 ? (
        <ul className="dashboard-priority-list">
          {items.slice(0, 5).map((item) => (
            <li key={`${item.held_ticker}-${item.candidate_ticker}`} className="priority-tone-neutral">
              <div className="dashboard-priority-label-row priority-tone-neutral">
                <span>{item.held_ticker} vs {item.candidate_ticker}</span>
                <strong>{item.swap_candidate_score}점</strong>
              </div>
              <div className="dashboard-priority-badges">
                <span className="dashboard-priority-badge priority-tone-neutral">{item.overlap_context}</span>
                <span className="dashboard-priority-badge priority-tone-neutral">검토 {item.review_points.length}개</span>
              </div>
              <p>{item.summary}</p>
              <p>{compactText(item.reasons, 2)}</p>
              <p>검토: {compactText(item.review_points, 2)}</p>
              <Link to="/portfolio" className="ticker-link">포트폴리오 검토로 이동</Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="dashboard-priority-empty">{emptyMessage}</p>
      )}
    </article>
  )
}

function EventExposureCard({
  items,
  emptyMessage,
}: {
  items: PMEventExposureItem[]
  emptyMessage: string
}) {
  return (
    <article className="dashboard-priority-card">
      <div className="dashboard-priority-head">
        <span className="dashboard-priority-kicker">{items.length > 0 ? `${items.length}건` : 'Clear'}</span>
        <strong>Event Exposure Review</strong>
      </div>

      {items.length > 0 ? (
        <ul className="dashboard-priority-list">
          {items.slice(0, 5).map((item) => (
            <li key={`${item.ticker}-${item.event_label}-${item.event_date}`} className="priority-tone-down">
              <div className="dashboard-priority-label-row priority-tone-down">
                <span>{item.ticker}</span>
                <strong>{item.event_label} · D-{item.days_until}</strong>
              </div>
              <div className="dashboard-priority-badges">
                <span className="dashboard-priority-badge priority-tone-down">리스크 {item.event_risk_score}</span>
                <span className="dashboard-priority-badge priority-tone-neutral">{item.event_date}</span>
              </div>
              <p>{item.summary}</p>
              <p>{compactText(item.reasons, 2)}</p>
              <p>검토: {compactText(item.review_points, 2)}</p>
              <Link to={`/ticker/${item.ticker}`} className="ticker-link">{item.ticker} 상세 보기</Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="dashboard-priority-empty">{emptyMessage}</p>
      )}
    </article>
  )
}

function TodayPriorityQueueCard({
  items,
  emptyMessage,
}: {
  items: PMPriorityQueueItem[]
  emptyMessage: string
}) {
  return (
    <article className="dashboard-priority-card">
      <div className="dashboard-priority-head">
        <span className="dashboard-priority-kicker">{items.length > 0 ? `TOP ${Math.min(items.length, 6)}` : 'Idle'}</span>
        <strong>Today Priority Queue</strong>
      </div>

      {items.length > 0 ? (
        <ul className="dashboard-priority-list">
          {items.slice(0, 6).map((item) => (
            <li key={`${item.priority_type}-${item.ticker}-${item.related_ticker ?? 'none'}`} className={queueTone(item.priority_type)}>
              <div className={`dashboard-priority-label-row ${queueTone(item.priority_type)}`}>
                <span>{priorityLabel(item.priority_type)}</span>
                <strong>{formatQueueValue(item)}</strong>
              </div>
              <div className="dashboard-priority-badges">
                <span className={`dashboard-priority-badge ${queueTone(item.priority_type)}`}>{item.today_priority_score}점</span>
                <span className="dashboard-priority-badge priority-tone-neutral">{item.ticker}{item.related_ticker ? ` · ${item.related_ticker}` : ''}</span>
              </div>
              <p>{item.summary}</p>
              <p>{compactText(item.reasons, 2)}</p>
              <Link to={queueDestination(item)} className="ticker-link">{queueLinkLabel(item)}</Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="dashboard-priority-empty">{emptyMessage}</p>
      )}
    </article>
  )
}

function compactText(lines: string[], limit: number): string {
  return lines.filter(Boolean).slice(0, limit).join(' · ')
}

function priorityLabel(priorityType: string): string {
  if (priorityType === 'swap_review') return 'Swap Review'
  if (priorityType === 'event_review') return 'Event Review'
  if (priorityType === 'decision_change') return 'Decision Change'
  if (priorityType === 'risk_warning') return 'Risk Warning'
  return 'Review'
}

function formatQueueValue(item: PMPriorityQueueItem): string {
  if (item.related_ticker) {
    return `${item.ticker} → ${item.related_ticker}`
  }
  return item.ticker
}

function queueTone(priorityType: string): string {
  if (priorityType === 'swap_review') return 'priority-tone-new'
  if (priorityType === 'event_review') return 'priority-tone-down'
  return 'priority-tone-neutral'
}

function queueDestination(item: PMPriorityQueueItem): string {
  if (item.destination.startsWith('/')) return item.destination
  if (item.destination === 'portfolio') return '/portfolio'
  return `/ticker/${item.ticker}`
}

function queueLinkLabel(item: PMPriorityQueueItem): string {
  if (item.destination === 'portfolio') return '포트폴리오 검토로 이동'
  return `${item.ticker} 상세 보기`
}
