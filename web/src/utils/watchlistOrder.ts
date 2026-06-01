export type WatchlistMoveDirection = 'up' | 'down'

export function moveTickerOrder(
  order: string[],
  activeId: string,
  overId: string,
): string[] {
  if (activeId === overId) {
    return order
  }

  const fromIndex = order.indexOf(activeId)
  const toIndex = order.indexOf(overId)

  if (fromIndex < 0 || toIndex < 0) {
    return order
  }

  const next = [...order]
  const [moved] = next.splice(fromIndex, 1)

  if (moved === undefined) {
    return order
  }

  next.splice(toIndex, 0, moved)
  return next
}

export function moveTickerOrderByKeyboard(
  order: string[],
  activeId: string,
  direction: WatchlistMoveDirection,
): string[] {
  const fromIndex = order.indexOf(activeId)

  if (fromIndex < 0) {
    return order
  }

  const toIndex = direction === 'up' ? fromIndex - 1 : fromIndex + 1

  if (toIndex < 0 || toIndex >= order.length) {
    return order
  }

  const next = [...order]
  const [moved] = next.splice(fromIndex, 1)

  if (moved === undefined) {
    return order
  }

  next.splice(toIndex, 0, moved)
  return next
}
