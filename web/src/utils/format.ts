export function parseNumericChange(value: string): number {
  const cleaned = value.replace('%', '').replace('+', '').trim()
  const num = parseFloat(cleaned)
  return isNaN(num) ? 0 : num
}

export function parsePrice(value: string): number {
  const cleaned = value.replace(/[^0-9.-]/g, '')
  const num = parseFloat(cleaned)
  return isNaN(num) ? 0 : num
}

export function changeColor(percent: number): string {
  if (percent > 0) return 'var(--color-up)'
  if (percent < 0) return 'var(--color-down)'
  return 'var(--color-neutral)'
}

export type SignalDirection = 'bullish' | 'neutral' | 'bearish'

export function signalLevel(percent: number): string {
  if (percent >= 3) return 'strong-up'
  if (percent >= 1) return 'up'
  if (percent > -1) return 'flat'
  if (percent > -3) return 'down'
  return 'strong-down'
}

export function extractSignalDirection(signal?: string): SignalDirection | undefined {
  if (!signal) return undefined
  const head = signal.split('|')[0]?.trim() ?? ''
  const directionToken = head.split(/[—-]/)[0]?.trim().toLowerCase() ?? ''
  if (!directionToken) return undefined
  if (/(매수|bull|long|상승)/i.test(directionToken)) return 'bullish'
  if (/(매도|bear|short|하락)/i.test(directionToken)) return 'bearish'
  if (/(중립|관찰|neutral)/i.test(directionToken)) return 'neutral'
  return undefined
}
