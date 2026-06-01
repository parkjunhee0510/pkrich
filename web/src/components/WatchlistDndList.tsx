import {
  memo,
  useCallback,
  useMemo,
  useState,
  type CSSProperties,
  type DragEvent,
  type HTMLAttributes,
  type KeyboardEvent,
} from 'react'
import type { TickerAnalysisData } from '../types'
import { moveTickerOrder, moveTickerOrderByKeyboard, type WatchlistMoveDirection } from '../utils/watchlistOrder'
import { WatchlistCard, type DensityMode } from './WatchlistTable'

type WatchlistDndListProps = {
  tickers: TickerAnalysisData[]
  accountSize: number
  density: DensityMode
  onOrderChange: (newOrder: string[]) => void
}

export function WatchlistDndList({
  tickers,
  accountSize,
  density,
  onOrderChange,
}: WatchlistDndListProps) {
  const [draggingTicker, setDraggingTicker] = useState<string | null>(null)
  const currentIds = useMemo(() => tickers.map((ticker) => ticker.ticker), [tickers])

  const commitOrderChange = useCallback(
    (nextOrder: string[]) => {
      if (nextOrder !== currentIds) {
        onOrderChange(nextOrder)
      }
    },
    [currentIds, onOrderChange],
  )

  return (
    <div className="watchlist-list" data-density={density}>
      {tickers.map((ticker) => (
        <NativeWatchlistCard
          key={ticker.ticker}
          ticker={ticker}
          accountSize={accountSize}
          density={density}
          currentIds={currentIds}
          isDragging={draggingTicker === ticker.ticker}
          onDraggingTickerChange={setDraggingTicker}
          onOrderChange={commitOrderChange}
        />
      ))}
    </div>
  )
}

const NativeWatchlistCard = memo(function NativeWatchlistCard({
  ticker,
  accountSize,
  density,
  currentIds,
  isDragging,
  onDraggingTickerChange,
  onOrderChange,
}: {
  ticker: TickerAnalysisData
  accountSize: number
  density: DensityMode
  currentIds: string[]
  isDragging: boolean
  onDraggingTickerChange: (ticker: string | null) => void
  onOrderChange: (newOrder: string[]) => void
}) {
  const tickerSymbol = ticker.ticker

  const handleDragStart = useCallback(
    (event: DragEvent<HTMLSpanElement>) => {
      event.dataTransfer.effectAllowed = 'move'
      event.dataTransfer.setData('text/plain', tickerSymbol)
      onDraggingTickerChange(tickerSymbol)
    },
    [onDraggingTickerChange, tickerSymbol],
  )

  const handleDragEnd = useCallback(() => {
    onDraggingTickerChange(null)
  }, [onDraggingTickerChange])

  const handleDragOver = useCallback(
    (event: DragEvent<HTMLElement>) => {
      const activeTicker = event.dataTransfer.getData('text/plain')
      if (!activeTicker || activeTicker === tickerSymbol) {
        return
      }

      event.preventDefault()
      event.dataTransfer.dropEffect = 'move'
    },
    [tickerSymbol],
  )

  const handleDrop = useCallback(
    (event: DragEvent<HTMLElement>) => {
      event.preventDefault()
      const activeTicker = event.dataTransfer.getData('text/plain')

      if (!activeTicker) {
        onDraggingTickerChange(null)
        return
      }

      onOrderChange(moveTickerOrder(currentIds, activeTicker, tickerSymbol))
      onDraggingTickerChange(null)
    },
    [currentIds, onDraggingTickerChange, onOrderChange, tickerSymbol],
  )

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLSpanElement>) => {
      if (!event.altKey) {
        return
      }

      const direction = getKeyboardMoveDirection(event.key)
      if (!direction) {
        return
      }

      const nextOrder = moveTickerOrderByKeyboard(currentIds, tickerSymbol, direction)
      if (nextOrder === currentIds) {
        return
      }

      event.preventDefault()
      onOrderChange(nextOrder)
    },
    [currentIds, onOrderChange, tickerSymbol],
  )

  const dragStyle: CSSProperties | undefined = isDragging
    ? { opacity: 0.55, zIndex: 10 }
    : undefined
  const dragHandleProps = {
    role: 'button',
    tabIndex: 0,
    draggable: true,
    'aria-grabbed': isDragging,
    'aria-label': `Reorder ${tickerSymbol}`,
    title: 'Drag or press Alt+Arrow keys to reorder',
    onDragStart: handleDragStart,
    onDragEnd: handleDragEnd,
    onKeyDown: handleKeyDown,
  } satisfies HTMLAttributes<HTMLSpanElement>
  const dropTargetProps = {
    onDragOver: handleDragOver,
    onDrop: handleDrop,
  } satisfies HTMLAttributes<HTMLElement>

  return (
    <WatchlistCard
      ticker={ticker}
      accountSize={accountSize}
      density={density}
      isDndEnabled
      dragStyle={dragStyle}
      dragHandleProps={dragHandleProps}
      dropTargetProps={dropTargetProps}
      isDragging={isDragging}
    />
  )
})

function getKeyboardMoveDirection(key: string): WatchlistMoveDirection | null {
  if (key === 'ArrowUp') {
    return 'up'
  }
  if (key === 'ArrowDown') {
    return 'down'
  }
  return null
}
