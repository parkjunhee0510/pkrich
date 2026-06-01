import { useId, type ReactNode } from 'react'

type InfoTooltipProps = {
  label?: string
  content: ReactNode
}

export function InfoTooltip({ label = 'i', content }: InfoTooltipProps) {
  const tooltipId = useId()

  return (
    <span className="info-tooltip">
      <button
        type="button"
        className="info-tooltip-trigger"
        aria-label={typeof content === 'string' ? content : '도움말 보기'}
        aria-describedby={tooltipId}
      >
        <span>{label}</span>
      </button>
      <span id={tooltipId} className="info-tooltip-bubble" role="tooltip">
        {content}
      </span>
    </span>
  )
}
