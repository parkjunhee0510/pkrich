import { Link } from 'react-router-dom'
import type { PMEventExposureItem, PMViewData, PMSwapCandidate } from '../types'

type PortfolioActionsReviewProps = {
  pmView?: PMViewData | null
}

const DEFAULT_EMPTY_STATES = {
  swap_candidates: 'No swap review items today. Current holdings do not have a stronger same-sector comparison candidate.',
  event_exposure_items: 'No near-term event exposure reviews today. Held names do not show immediate event pressure.',
} as const

export function PortfolioActionsReview({ pmView }: PortfolioActionsReviewProps) {
  if (!pmView) {
    return null
  }

  const swapCandidates = pmView.swap_candidates ?? []
  const eventExposureItems = pmView.event_exposure_items ?? []
  const emptyStates = {
    swap_candidates: pmView.empty_states?.swap_candidates || DEFAULT_EMPTY_STATES.swap_candidates,
    event_exposure_items: pmView.empty_states?.event_exposure_items || DEFAULT_EMPTY_STATES.event_exposure_items,
  }

  return (
    <section className="dashboard-priority-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>Portfolio Review</h3>
          <p className="section-kicker">
            Why held names are on today&apos;s PM review list
            {pmView.as_of ? ` as of ${pmView.as_of}` : ''}. Review context only; official buy/watch/avoid stays unchanged.
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
        <span className="dashboard-priority-kicker">{items.length > 0 ? `TOP ${Math.min(items.length, 5)}` : 'CLEAR'}</span>
        <strong>Swap Review</strong>
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
                  vs{' '}
                  <Link to={`/ticker/${item.candidate_ticker}`} className="ticker-link">
                    {item.candidate_ticker}
                  </Link>
                </span>
                <strong>{item.swap_candidate_score} pts</strong>
              </div>
              <div className="dashboard-priority-badges">
                <span className="dashboard-priority-badge priority-tone-neutral">{item.overlap_context}</span>
                <span className="dashboard-priority-badge priority-tone-neutral">{item.review_points.length} review points</span>
              </div>
              <p>{item.summary}</p>
              <p>{compactText(item.reasons, 3)}</p>
              <p>Check next: {compactText(item.review_points, 2)}</p>
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
        <span className="dashboard-priority-kicker">{items.length > 0 ? `${items.length} ITEMS` : 'CLEAR'}</span>
        <strong>Event Exposure Review</strong>
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
                <span className="dashboard-priority-badge priority-tone-down">Risk {item.event_risk_score}</span>
                <span className="dashboard-priority-badge priority-tone-neutral">{item.event_date || 'Date pending'}</span>
              </div>
              <p>{item.summary}</p>
              <p>{compactText(item.reasons, 3)}</p>
              <p>Check next: {compactText(item.review_points, 2)}</p>
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
  return lines.filter(Boolean).slice(0, limit).join(' | ')
}

function formatDaysUntil(value: number): string {
  if (!Number.isFinite(value) || value < 0) {
    return 'Schedule check'
  }
  return `D-${value}`
}
