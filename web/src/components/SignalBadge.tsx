import { signalLevel, type SignalDirection } from '../utils/format'

const LABELS: Record<string, string> = {
  'strong-up': '강한 상승',
  'up': '상승',
  'flat': '보합',
  'down': '하락',
  'strong-down': '강한 하락',
}

function signalLevelFromDirection(direction?: SignalDirection): string | undefined {
  if (direction === 'bullish') return 'up'
  if (direction === 'bearish') return 'down'
  if (direction === 'neutral') return 'flat'
  return undefined
}

export function SignalBadge({
  changePercent,
  signalDirection,
}: {
  changePercent: number
  signalDirection?: SignalDirection
}) {
  const level = signalLevelFromDirection(signalDirection) ?? signalLevel(changePercent)
  return <span className={`signal-badge signal-${level}`}>{LABELS[level]}</span>
}
