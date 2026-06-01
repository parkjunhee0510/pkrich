import type { PortfolioHoldingInput } from '../types'

export type PortfolioSaveOptions = {
  allowTruncate?: boolean
}

export function resolvePortfolioSaveHoldings(
  existingHoldings: PortfolioHoldingInput[],
  incomingHoldings: PortfolioHoldingInput[],
  options: PortfolioSaveOptions = {},
): PortfolioHoldingInput[] {
  if (!options.allowTruncate && incomingHoldings.length < existingHoldings.length) {
    throw new Error('Refusing to overwrite portfolio with fewer lots without an explicit delete action.')
  }

  return incomingHoldings
}
