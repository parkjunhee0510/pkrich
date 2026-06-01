import { Link } from 'react-router-dom'

import type { TodayPriorityQueueItem, TodayPriorityQueueResult } from '../utils/todayPriorityQueue'

type TodayPriorityQueueProps = {
  queue: TodayPriorityQueueResult
}

export function TodayPriorityQueue({ queue }: TodayPriorityQueueProps) {
  return (
    <section
      className="dashboard-panel-section today-priority-queue-section"
      aria-labelledby="today-priority-queue-title"
    >
      <div className="section-header-with-kicker today-priority-queue-head">
        <div>
          <h3 id="today-priority-queue-title">오늘 점검 큐</h3>
          <p className="section-kicker">
            리스크, 기회, 근거 상태를 합쳐 오늘 먼저 열어볼 종목을 정리합니다.
          </p>
        </div>
        <div className="today-priority-queue-meta" role="group" aria-label="오늘 점검 큐 상태">
          <span>{queue.asOf}</span>
          <span>{queue.evidenceHealthLabel}</span>
          {queue.qualityWarnings.length > 0 ? (
            <span>경고 {queue.qualityWarnings.length}개</span>
          ) : null}
        </div>
      </div>

      {queue.items.length === 0 ? (
        <p className="today-priority-empty">{queue.emptyLabel}</p>
      ) : (
        <div className="today-priority-list">
          {queue.items.map((item) => (
            <TodayPriorityQueueRow key={item.id} item={item} />
          ))}
        </div>
      )}
    </section>
  )
}

function TodayPriorityQueueRow({ item }: { item: TodayPriorityQueueItem }) {
  const primaryReason = item.reasons[0] ?? item.nextCheck

  return (
    <article
      className={`today-priority-row today-priority-tone-${item.tone}`}
      aria-label={`${item.ticker} ${item.priorityLabel}`}
    >
      <div className="today-priority-row-main">
        <div className="today-priority-title-row">
          <Link to={item.destination} className="ticker-link today-priority-ticker">
            {item.ticker}
          </Link>
          <span className="today-priority-name">{item.name}</span>
          <span className="today-priority-action">{item.officialAction}</span>
        </div>
        <strong className="today-priority-label">{item.priorityLabel}</strong>
        <p className="today-priority-reason">{primaryReason}</p>
      </div>

      <div
        className="today-priority-badge-column"
        role="group"
        aria-label={`${item.ticker} 점검 신호`}
      >
        <span
          className={`today-priority-badge today-priority-badge-risk today-priority-badge-risk-${item.riskLevel}`}
        >
          {item.riskLabel}
        </span>
        <span
          className={`today-priority-badge today-priority-badge-opportunity today-priority-badge-opportunity-${item.opportunityLevel}`}
        >
          {item.opportunityLabel}
        </span>
        <span
          className={`today-priority-badge today-priority-badge-evidence today-priority-badge-evidence-${statusClassName(
            item.evidenceStatus,
          )}`}
        >
          {item.evidenceLabel}
        </span>
      </div>

      <div className="today-priority-score-block">
        <span>Score</span>
        <strong>{Math.round(item.priorityScore)}</strong>
        <Link to={item.destination} className="today-priority-detail-link">
          {item.ticker} 상세
        </Link>
      </div>
    </article>
  )
}

function statusClassName(status: TodayPriorityQueueItem['evidenceStatus']): string {
  return status.replace(/_/g, '-')
}
