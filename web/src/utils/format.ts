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

export function signalLevel(percent: number): string {
  if (percent >= 3) return 'strong-up'
  if (percent >= 1) return 'up'
  if (percent > -1) return 'flat'
  if (percent > -3) return 'down'
  return 'strong-down'
}
