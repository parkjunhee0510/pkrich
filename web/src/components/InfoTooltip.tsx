import type { ReactNode } from 'react'

type InfoTooltipProps = {
  label?: string
  content: ReactNode
}

export function InfoTooltip({ label = 'i', content }: InfoTooltipProps) {
  return (
    <span className="info-tooltip" tabIndex={0} aria-label={typeof content === 'string' ? content : undefined}>
      <span className="info-tooltip-trigger" aria-hidden="true">
        {label}
      </span>
      <span className="info-tooltip-bubble" role="tooltip">
        {content}
      </span>
    </span>
  )
}
