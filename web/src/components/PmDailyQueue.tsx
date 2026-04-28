import { Link } from 'react-router-dom'
import type { PMEventExposureItem, PMPriorityQueueItem, PMSwapCandidate, PMViewData } from '../types'

type PmDailyQueueProps = {
  pmView?: PMViewData | null
}

const DEFAULT_EMPTY_STATES = {
  swap_candidates: '오늘은 교체 검토 후보가 없습니다. 현재 보유 종목의 확신도와 이벤트 일정이 비교적 안정적입니다.',
  event_exposure_items: '오늘은 별도로 점검할 이벤트 노출이 없습니다.',
  today_priority_queue: '오늘 바로 확인할 PM 검토 항목이 없습니다. 아래 대시보드 섹션을 순서대로 확인하면 됩니다.',
} as const

const MAX_DISPLAYABLE_DAYS = 30

export function PmDailyQueue({ pmView }: PmDailyQueueProps) {
  if (!pmView) {
    return null
  }

  const swapCandidates = pmView.swap_candidates ?? []
  const eventExposureItems = pmView.event_exposure_items ?? []
  const todayPriorityQueue = pmView.today_priority_queue ?? []
  const hasRealData = swapCandidates.length > 0 || eventExposureItems.length > 0 || todayPriorityQueue.length > 0

  if (!hasRealData) {
    return null
  }

  const emptyStates = {
    swap_candidates: pmView.empty_states?.swap_candidates || DEFAULT_EMPTY_STATES.swap_candidates,
    event_exposure_items: pmView.empty_states?.event_exposure_items || DEFAULT_EMPTY_STATES.event_exposure_items,
    today_priority_queue: pmView.empty_states?.today_priority_queue || DEFAULT_EMPTY_STATES.today_priority_queue,
  }

  return (
    <section className="dashboard-priority-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>PM 검토 큐</h3>
          <p className="section-kicker">
            포트폴리오에서 오늘 먼저 확인할 검토 항목만 위에 모았습니다.
            {pmView.as_of ? ` 기준일 ${pmView.as_of}` : ''}
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
        <span className="dashboard-priority-kicker">{items.length > 0 ? `TOP ${Math.min(items.length, 5)}` : '안정'}</span>
        <strong>교체 검토 후보</strong>
      </div>

      {items.length > 0 ? (
        <ul className="dashboard-priority-list">
          {items.slice(0, 3).map((item) => (
            <li key={`${item.held_ticker}-${item.candidate_ticker}`} className="priority-tone-neutral">
              <div className="dashboard-priority-label-row priority-tone-neutral">
                <span>{item.held_ticker} vs {item.candidate_ticker}</span>
                <strong>{item.swap_candidate_score}점</strong>
              </div>
              <p>{item.summary}</p>
              <Link to="/portfolio" className="ticker-link">포트폴리오에서 이어서 보기</Link>
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
        <span className="dashboard-priority-kicker">{items.length > 0 ? `${items.length}건` : '안정'}</span>
        <strong>이벤트 노출 점검</strong>
      </div>

      {items.length > 0 ? (
        <ul className="dashboard-priority-list">
          {items.slice(0, 3).map((item) => (
            <li key={`${item.ticker}-${item.event_label}-${item.event_date}`} className="priority-tone-down">
              <div className="dashboard-priority-label-row priority-tone-down">
                <span>{item.ticker}</span>
                <strong>{item.event_label} · {formatDaysUntil(item.days_until)}</strong>
              </div>
              <p>{item.summary}</p>
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
        <span className="dashboard-priority-kicker">{items.length > 0 ? `TOP ${Math.min(items.length, 4)}` : '비어 있음'}</span>
        <strong>오늘 우선 검토 큐</strong>
      </div>

      {items.length > 0 ? (
        <ul className="dashboard-priority-list">
          {items.slice(0, 4).map((item) => (
            <li key={`${item.priority_type}-${item.ticker}-${item.related_ticker ?? 'none'}`} className={queueTone(item.priority_type)}>
              <div className={`dashboard-priority-label-row ${queueTone(item.priority_type)}`}>
                <span>{priorityLabel(item.priority_type)} · {formatQueueValue(item)}</span>
                <strong>{item.today_priority_score}점</strong>
              </div>
              <p>{item.summary}</p>
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

function formatDaysUntil(value: number): string {
  if (!Number.isFinite(value) || value < 0) {
    return '일정 확인 필요'
  }
  if (value <= MAX_DISPLAYABLE_DAYS) {
    return `D-${value}`
  }
  return '일정 여유'
}

function priorityLabel(priorityType: string): string {
  if (priorityType === 'swap_review') return '교체 검토'
  if (priorityType === 'event_review') return '이벤트 점검'
  if (priorityType === 'decision_change') return '판단 변화'
  if (priorityType === 'risk_warning') return '리스크 점검'
  return '검토'
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
  if (item.destination === 'portfolio') return '포트폴리오에서 이어서 보기'
  return `${item.ticker} 상세 보기`
}
