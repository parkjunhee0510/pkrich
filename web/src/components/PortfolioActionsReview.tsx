import { Link } from 'react-router-dom'
import type { PMEventExposureItem, PMViewData, PMSwapCandidate } from '../types'

type PortfolioActionsReviewProps = {
  pmView?: PMViewData | null
}

const DEFAULT_EMPTY_STATES = {
  swap_candidates: '오늘은 동일 섹터 내에서 더 나은 교체 후보가 없습니다.',
  event_exposure_items: '오늘은 별도로 점검할 단기 이벤트 노출이 없습니다.',
} as const

const MAX_DISPLAYABLE_DAYS = 30

export function PortfolioActionsReview({ pmView }: PortfolioActionsReviewProps) {
  if (!pmView) {
    return null
  }

  const swapCandidates = pmView.swap_candidates ?? []
  const eventExposureItems = pmView.event_exposure_items ?? []
  const hasRealData = swapCandidates.length > 0 || eventExposureItems.length > 0 || (pmView.today_priority_queue?.length ?? 0) > 0

  if (!hasRealData) {
    return null
  }

  const emptyStates = {
    swap_candidates: pmView.empty_states?.swap_candidates || DEFAULT_EMPTY_STATES.swap_candidates,
    event_exposure_items: pmView.empty_states?.event_exposure_items || DEFAULT_EMPTY_STATES.event_exposure_items,
  }

  return (
    <section className="dashboard-priority-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>포트폴리오 검토</h3>
          <p className="section-kicker">
            오늘 PM 검토 목록에 오른 보유 종목의 이유를 정리합니다.
            {pmView.as_of ? ` 기준일 ${pmView.as_of}` : ''}. 검토 참고용 정보이며 공식 buy/watch/avoid 판단은 유지됩니다.
          </p>
        </div>
      </div>

      <div className="dashboard-priority-grid">
        <SwapReviewCard items={swapCandidates} emptyMessage={emptyStates.swap_candidates} />
        <EventExposureCard items={eventExposureItems} emptyMessage={emptyStates.event_exposure_items} />
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
          {items.slice(0, 5).map((item) => (
            <li key={`${item.held_ticker}-${item.candidate_ticker}`} className="priority-tone-neutral">
              <div className="dashboard-priority-label-row priority-tone-neutral">
                <span>
                  <Link to={`/ticker/${item.held_ticker}`} className="ticker-link">
                    {item.held_ticker}
                  </Link>{' '}
                  대비{' '}
                  <Link to={`/ticker/${item.candidate_ticker}`} className="ticker-link">
                    {item.candidate_ticker}
                  </Link>
                </span>
                <strong>{item.swap_candidate_score}점</strong>
              </div>
              <div className="dashboard-priority-badges">
                <span className="dashboard-priority-badge priority-tone-neutral">{item.overlap_context}</span>
                <span className="dashboard-priority-badge priority-tone-neutral">검토 포인트 {item.review_points.length}개</span>
              </div>
              <p>{item.summary}</p>
              <p>{compactText(item.reasons, 3)}</p>
              <p>다음 확인: {compactText(item.review_points, 2)}</p>
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
          {items.slice(0, 5).map((item) => (
            <li key={`${item.ticker}-${item.event_label}-${item.event_date}`} className="priority-tone-down">
              <div className="dashboard-priority-label-row priority-tone-down">
                <span>
                  <Link to={`/ticker/${item.ticker}`} className="ticker-link">
                    {item.ticker}
                  </Link>
                </span>
                <strong>
                  {item.event_label} | {formatDaysUntil(item.days_until)}
                </strong>
              </div>
              <div className="dashboard-priority-badges">
                <span className="dashboard-priority-badge priority-tone-down">리스크 {item.event_risk_score}</span>
                <span className="dashboard-priority-badge priority-tone-neutral">{item.event_date || '일정 확인 필요'}</span>
              </div>
              <p>{item.summary}</p>
              <p>{compactText(item.reasons, 3)}</p>
              <p>다음 확인: {compactText(item.review_points, 2)}</p>
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

function formatDaysUntil(value: number): string {
  if (!Number.isFinite(value) || value < 0) {
    return '일정 확인 필요'
  }
  if (value <= MAX_DISPLAYABLE_DAYS) {
    return `D-${value}`
  }
  return '추후 일정'
}
