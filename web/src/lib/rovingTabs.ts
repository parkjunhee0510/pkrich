export function getRovingTabIndex(key: string, currentIndex: number, count: number): number | null {
  if (count <= 0) return null
  const safeIndex = Math.min(Math.max(currentIndex, 0), count - 1)

  if (key === 'ArrowRight' || key === 'ArrowDown') {
    return (safeIndex + 1) % count
  }
  if (key === 'ArrowLeft' || key === 'ArrowUp') {
    return (safeIndex - 1 + count) % count
  }
  if (key === 'Home') {
    return 0
  }
  if (key === 'End') {
    return count - 1
  }
  return null
}
