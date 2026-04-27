import { Link } from 'react-router-dom'
import type { CommandDeskModel, CommandQueueItem, CommandWorkspaceCardModel } from '../utils/commandDesk'

type DailyCommandQueueProps = {
  model: CommandDeskModel
}

export function DailyCommandQueue({ model }: DailyCommandQueueProps) {
  const hasQueue = model.queueItems.length > 0

  return (
    <section className="cozy-premium-command-desk" aria-labelledby="command-desk-title">
      <div className="cozy-premium-command-hero">
        <div className="cozy-premium-command-copy">
          <span className="cozy-eyebrow">
            <span className={`dot ${model.counts.urgent > 0 ? 'bad' : model.counts.watch > 0 ? 'warn' : ''}`} />
            Daily Command Queue
          </span>
          <h2 id="command-desk-title" className="cozy-headline">
            오늘 먼저 볼 일만 정리했습니다.
          </h2>
          <p className="cozy-impl">
            {model.asOf} 기준 · {model.marketLabel}
          </p>
          <div className="cozy-premium-command-counts" aria-label="오늘 우선순위 요약">
            <span>
              <b>{model.counts.urgent}</b>
              긴급
            </span>
            <span>
              <b>{model.counts.watch}</b>
              관찰
            </span>
            <span>
              <b>{model.counts.info}</b>
              참고
            </span>
          </div>
        </div>

        <div className="cozy-premium-command-panel">
          <div className="cozy-premium-command-panel-head">
            <span>Action Queue</span>
            <strong>{hasQueue ? `${model.queueItems.length}건` : 'Quiet'}</strong>
          </div>

          {hasQueue ? (
            <div className="cozy-premium-action-list">
              {model.queueItems.map((item) => (
                <CommandActionCard key={item.id} item={item} />
              ))}
            </div>
          ) : (
            <CommandEmptyState title={model.emptyTitle} body={model.emptyBody} />
          )}
        </div>
      </div>

      <CommandWorkspaceGrid cards={model.workspaces} />
    </section>
  )
}

function CommandActionCard({ item }: { item: CommandQueueItem }) {
  return (
    <article className={`cozy-premium-action-card tone-${item.tone}`}>
      <div className="cozy-premium-action-card-main">
        <div>
          <span className="cozy-premium-action-type">{item.typeLabel}</span>
          <h3>{item.title}</h3>
        </div>
        {typeof item.score === 'number' ? <strong className="cozy-premium-action-score">{Math.round(item.score)}점</strong> : null}
      </div>
      <p>{item.summary}</p>
      {item.reasons.length > 0 ? (
        <ul>
          {item.reasons.map((reason) => (
            <li key={`${item.id}-${reason}`}>{reason}</li>
          ))}
        </ul>
      ) : null}
      <Link className="cozy-premium-action-link" to={item.destination}>
        {item.ticker ? `${item.ticker} 확인하기` : '자세히 보기'}
      </Link>
    </article>
  )
}

function CommandWorkspaceGrid({ cards }: { cards: CommandWorkspaceCardModel[] }) {
  return (
    <div className="cozy-premium-workspace-grid" aria-label="워크스페이스 바로가기">
      {cards.map((card) => (
        <CommandWorkspaceCard key={card.id} card={card} />
      ))}
    </div>
  )
}

function CommandWorkspaceCard({ card }: { card: CommandWorkspaceCardModel }) {
  const content = (
    <>
      <span className="cozy-premium-workspace-eyebrow">{card.eyebrow}</span>
      <div className="cozy-premium-workspace-title-row">
        <h3>{card.title}</h3>
        <strong>{card.metric}</strong>
      </div>
      <p>{card.summary}</p>
    </>
  )

  if (card.disabled) {
    return <article className={`cozy-premium-workspace-card tone-${card.tone} is-disabled`}>{content}</article>
  }

  if (card.href.startsWith('#')) {
    return (
      <a className={`cozy-premium-workspace-card tone-${card.tone}`} href={card.href}>
        {content}
      </a>
    )
  }

  return (
    <Link className={`cozy-premium-workspace-card tone-${card.tone}`} to={card.href}>
      {content}
    </Link>
  )
}

function CommandEmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="cozy-premium-command-empty">
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  )
}
