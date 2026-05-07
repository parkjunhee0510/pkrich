import { useId, useState } from 'react'
import { Link } from 'react-router-dom'

import type { ActionChangeFeedEntry, ActionChangeFeedResult } from '../utils/actionChangeFeed'
import { SearchEvidenceBadge } from './SearchEvidenceBadge'

const VISIBLE_ENTRY_LIMIT = 8

type ActionChangeFeedProps = {
  feed: ActionChangeFeedResult
}

export function ActionChangeFeed({ feed }: ActionChangeFeedProps) {
  const titleId = useId()
  const gridId = useId()
  const feedKey = buildFeedKey(feed)
  const [expandedFeedKey, setExpandedFeedKey] = useState<string | null>(null)
  const expanded = expandedFeedKey === feedKey
  const visibleEntries = expanded ? feed.entries : feed.entries.slice(0, VISIBLE_ENTRY_LIMIT)
  const hasHiddenEntries = feed.entries.length > VISIBLE_ENTRY_LIMIT

  return (
    <section
      className="dashboard-panel-section action-change-feed-section"
      aria-labelledby={titleId}
    >
      <div className="section-header-with-kicker action-change-feed-head">
        <div>
          <h3 id={titleId}>오늘 판단 변화</h3>
          <p className="section-kicker">
            {feed.previousDate
              ? `${feed.previousDate} 대비 ${feed.currentDate}`
              : `${feed.currentDate} 기준`}
          </p>
        </div>
        {feed.hasPreviousDay && feed.entries.length > 0 ? (
          <span className="action-change-count">{feed.entries.length}개</span>
        ) : null}
      </div>

      {!feed.hasPreviousDay ? (
        <p className="action-change-empty">직전 리포트가 없어 변화 비교를 시작할 수 없습니다.</p>
      ) : feed.entries.length === 0 ? (
        <p className="action-change-empty">오늘 공식 판단 변화는 크지 않습니다.</p>
      ) : (
        <>
          <div id={gridId} className="action-change-grid">
            {visibleEntries.map((entry) => (
              <ActionChangeCard key={entry.id} entry={entry} />
            ))}
          </div>
          {hasHiddenEntries ? (
            <button
              type="button"
              className="secondary-action-button action-change-toggle"
              aria-controls={gridId}
              aria-expanded={expanded}
              onClick={() =>
                setExpandedFeedKey((value) => (value === feedKey ? null : feedKey))
              }
            >
              {expanded ? '접기' : '전체 보기'}
            </button>
          ) : null}
        </>
      )}
    </section>
  )
}

function ActionChangeCard({ entry }: { entry: ActionChangeFeedEntry }) {
  return (
    <article
      className={`action-change-card ${typeClassName(entry.type)} ${stanceClassName(entry.tone)}`}
    >
      <div className="action-change-card-head">
        <div className="action-change-title-stack">
          <Link to={`/ticker/${entry.ticker}`} className="ticker-link action-change-ticker">
            {entry.ticker}
          </Link>
          <span className="action-change-name">{entry.name}</span>
          <span className="action-change-sector">{entry.sector}</span>
        </div>
        <span className={`action-change-primary-badge ${stanceClassName(entry.tone)}`}>
          {entry.primaryLabel}
        </span>
      </div>

      <div className="action-change-meta-row">
        <span>{entry.secondaryLabel}</span>
        {entry.evidenceBadge ? <SearchEvidenceBadge badge={entry.evidenceBadge} /> : null}
        {entry.addedRisks.length > 0 ? (
          <span className="action-change-risk-badge">
            새 리스크 {entry.addedRisks.length}개
          </span>
        ) : null}
      </div>

      <p className="action-change-summary">{entry.summary}</p>

      {entry.addedRisks[0] ? (
        <p className="action-change-risk-note">리스크: {entry.addedRisks[0]}</p>
      ) : null}
    </article>
  )
}

function buildFeedKey(feed: ActionChangeFeedResult): string {
  return JSON.stringify([
    feed.currentDate,
    feed.previousDate,
    feed.entries.length,
    feed.entries.map((entry) => entry.id),
  ])
}

function typeClassName(type: ActionChangeFeedEntry['type']): string {
  return `action-change-type-${type.replace(/_/g, '-')}`
}

function stanceClassName(tone: ActionChangeFeedEntry['tone']): string {
  return `action-change-stance-${tone}`
}
