import { signalLevel } from '../utils/format'

const LABELS: Record<string, string> = {
  'strong-up': '강한 상승',
  'up': '상승',
  'flat': '보합',
  'down': '하락',
  'strong-down': '급락',
}

export function SignalBadge({ changePercent }: { changePercent: number }) {
  const level = signalLevel(changePercent)
  return <span className={`signal-badge signal-${level}`}>{LABELS[level]}</span>
}
