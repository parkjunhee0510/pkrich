import { describe, expect, it } from 'vitest'
import { moveTickerOrder, moveTickerOrderByKeyboard } from './watchlistOrder'

describe('watchlist order helpers', () => {
  it('moves the active ticker to the hovered ticker position without mutating the input', () => {
    const order = ['AAPL', 'AMD', 'IONQ', 'RKLB']

    const next = moveTickerOrder(order, 'AMD', 'RKLB')

    expect(next).toEqual(['AAPL', 'IONQ', 'RKLB', 'AMD'])
    expect(order).toEqual(['AAPL', 'AMD', 'IONQ', 'RKLB'])
  })

  it('keeps the same order when drag ids are missing or unchanged', () => {
    const order = ['AAPL', 'AMD', 'IONQ']

    expect(moveTickerOrder(order, 'AMD', 'AMD')).toBe(order)
    expect(moveTickerOrder(order, 'MSFT', 'AMD')).toBe(order)
    expect(moveTickerOrder(order, 'AMD', 'MSFT')).toBe(order)
  })

  it('moves a ticker with keyboard up/down commands and clamps at the edges', () => {
    const order = ['AAPL', 'AMD', 'IONQ']

    expect(moveTickerOrderByKeyboard(order, 'AMD', 'up')).toEqual(['AMD', 'AAPL', 'IONQ'])
    expect(moveTickerOrderByKeyboard(order, 'AMD', 'down')).toEqual(['AAPL', 'IONQ', 'AMD'])
    expect(moveTickerOrderByKeyboard(order, 'AAPL', 'up')).toBe(order)
    expect(moveTickerOrderByKeyboard(order, 'IONQ', 'down')).toBe(order)
  })
})
