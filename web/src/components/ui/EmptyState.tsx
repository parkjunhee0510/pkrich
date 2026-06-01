import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { Card } from './Card'

type EmptyStateProps = {
  title: string
  description?: ReactNode
  action?: ReactNode
  tone?: 'default' | 'warning' | 'error'
  className?: string
}

export function EmptyState({
  title,
  description,
  action,
  tone = 'default',
  className,
}: EmptyStateProps) {
  return (
    <Card as="section" className={cn('ui-empty-state', `ui-empty-state-${tone}`, className)} aria-live="polite">
      <div className="ui-empty-state-mark" aria-hidden="true" />
      <div className="ui-empty-state-copy">
        <strong>{title}</strong>
        {description ? <p>{description}</p> : null}
      </div>
      {action ? <div className="ui-empty-state-action">{action}</div> : null}
    </Card>
  )
}
