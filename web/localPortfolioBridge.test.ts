import { describe, expect, it } from 'vitest'

import { resolvePortfolioSaveHoldings } from './src/utils/localPortfolioSave'
import type { PortfolioHoldingInput } from './src/types'

const existingHoldings: PortfolioHoldingInput[] = [
  { ticker: 'AAPL', shares: 12, avg_cost: 150, currency: 'USD' },
  { ticker: 'AMD', shares: 5, avg_cost: 100, currency: 'USD' },
]

describe('local portfolio bridge', () => {
  it('allows full-list ticker edits without delete approval', () => {
    const editedHoldings: PortfolioHoldingInput[] = [
      { ticker: 'PLUG', shares: 12, avg_cost: 3.25, currency: 'USD' },
      { ticker: 'AMD', shares: 5, avg_cost: 100, currency: 'USD' },
    ]

    expect(resolvePortfolioSaveHoldings(existingHoldings, editedHoldings)).toEqual(editedHoldings)
  })

  it('refuses a shorter save payload unless a row deletion was explicit', () => {
    const truncatedHoldings: PortfolioHoldingInput[] = [
      { ticker: 'PLUG', shares: 47, avg_cost: 2.88, currency: 'USD' },
    ]

    expect(() => resolvePortfolioSaveHoldings(existingHoldings, truncatedHoldings)).toThrow(/explicit delete/i)
  })

  it('allows shorter save payloads when the UI marked an intentional deletion', () => {
    const remainingHoldings: PortfolioHoldingInput[] = [
      { ticker: 'AAPL', shares: 12, avg_cost: 150, currency: 'USD' },
    ]

    expect(resolvePortfolioSaveHoldings(existingHoldings, remainingHoldings, { allowTruncate: true })).toEqual(
      remainingHoldings,
    )
  })
})
