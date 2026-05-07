import { useId } from 'react'
import { Link } from 'react-router-dom'

import type { TodayDecisionStripEntry, TodayDecisionStripResult } from '../utils/todayDecisionStrip'
import { SearchEvidenceBadge } from './SearchEvidenceBadge'

type TodayDecisionStripProps = {
  strip: TodayDecisionStripResult
}

export function TodayDecisionStrip({ strip }: TodayDecisionStripProps) {
  const titleId = useId()

  return (
    <section className="dashboard-panel-section today-decision-strip-section" aria-labelledby={titleId}>
      <div className="section-header-with-kicker today-decision-strip-head">
        <div>
          <h3 id={titleId}>오늘 먼저 볼 판단</h3>
          <p className="section-kicker">
            {strip.previousDate
              ? `${strip.previousDate} 대비 ${strip.currentDate}`
              : `${strip.currentDate} 기준`}
          </p>
        </div>
        {strip.entries.length > 0 ? (
          <span className="today-decision-count">{strip.entries.length}개</span>
        ) : null}
      </div>

      {strip.entries.length === 0 ? (
        <p className="today-decision-empty">오늘 우선 확인할 판단 변화가 없습니다.</p>
      ) : (
        <div className="today-decision-grid">
          {strip.entries.map((entry) => (
            <TodayDecisionCard key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </section>
  )
}

function TodayDecisionCard({ entry }: { entry: TodayDecisionStripEntry }) {
  return (
    <article
      className={[
        'today-decision-card',
        `today-decision-kind-${entry.kind.replace(/_/g, '-')}`,
        `today-decision-stance-${entry.stance}`,
      ].join(' ')}
    >
      <div className="today-decision-card-head">
        <span className="today-decision-category">{entry.categoryLabel}</span>
        <span className={`today-decision-quality-badge ${entry.qualityClassName}`}>
          {entry.qualityLabel}
        </span>
        {entry.evidenceBadge ? <SearchEvidenceBadge badge={entry.evidenceBadge} /> : null}
      </div>

      <div className="today-decision-title-row">
        <Link to={`/ticker/${entry.ticker}`} className="ticker-link today-decision-ticker">
          {entry.ticker}
        </Link>
        <span className="today-decision-name">{entry.name}</span>
      </div>

      <strong className="today-decision-title">{entry.title}</strong>
      <p className="today-decision-supporting-line">{entry.supportingLine}</p>

      <div className="today-decision-meta-row">
        <span>{entry.qualityDetail}</span>
        {entry.metricLabel ? <span>{entry.metricLabel}</span> : null}
        <span>{entry.sector}</span>
      </div>
    </article>
  )
}
