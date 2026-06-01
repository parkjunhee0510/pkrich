# Portfolio Quick Edit Design

## Goal

Make the portfolio edit mode faster and less click-heavy. The current editor groups lots by ticker and requires opening each group before editing individual lots. The improved editor should make common edits visible immediately while preserving the existing local portfolio save flow.

## Approved Approach

Use a single-screen quick edit layout.

- Show a compact holdings summary at the top of edit mode.
- Show every lot as an editable row immediately instead of hiding rows behind collapsed ticker groups.
- Keep the existing save, cancel, validation, and `useLocalPortfolioEditor` data flow.
- Keep lot-level editing because the backend contract stores holdings as lots, not only aggregated positions.

## UI Behavior

When the user enters edit mode:

- `draftHoldings` is initialized from `portfolioStatus.holdings`.
- If there are no holdings, one empty lot row is shown automatically so first-time setup is direct.
- Save and cancel controls stay visible at the top of the editor.
- A small edit summary shows total lot count, changed lot count, and aggregated ticker count.
- The aggregate ticker summary lists total shares, weighted average cost, and lot count per ticker.

Each editable lot row supports:

- Ticker selection from the available ticker list
- Shares
- Average cost
- Currency
- Delete

Ticker options come from the latest research tickers, existing saved holdings, current draft holdings, and current portfolio positions. The ticker field does not accept arbitrary saved text input; the user chooses a listed ticker by clicking an option. A filter field may narrow the list, but only clicked list items update the lot ticker.

When a ticker is selected for a new or otherwise empty-cost lot, average cost defaults to the current market price for that ticker. Current price lookup uses portfolio positions first (`market_price`), then falls back to the latest research snapshot (`data_snapshot.Price`). If the current average cost still matches the previous ticker's auto-filled price, switching tickers refreshes it to the new ticker price. Existing manually entered non-zero average costs are preserved so saved lots are not accidentally overwritten.

The add-lot action appends a new row at the bottom and keeps the editor in the same screen.

## Data Flow

No new persistence layer is introduced.

- Read: `useLocalPortfolioEditor().status.holdings`
- Draft state: `Portfolio.tsx` local state
- Save: existing `saveHoldings(draftHoldings)`
- Validation: existing `validateDraftHoldings`
- Refresh: existing `onSaved` callback

## Error Handling

Validation remains client-side before save:

- At least one lot is required.
- Ticker must match the existing ticker pattern.
- Shares must be greater than zero.
- Average cost must be zero or greater.

Save errors continue to use existing toast messaging.

## Styling

Use existing portfolio editor class family in `components.css`. The new layout should be dense, readable, and responsive:

- Summary chips wrap on narrow widths.
- Lot rows use explicit field labels so mobile layout is understandable.
- Buttons preserve the current primary/secondary action styling.

## Testing

Add focused tests around the portfolio edit flow:

- Edit mode renders existing lots immediately without expanding groups.
- Empty local portfolio shows a starter row.
- Selecting a ticker for an empty-cost lot fills average cost from current price.
- Switching from one auto-filled ticker to another refreshes average cost to the newly selected ticker price.
- Changing a lot updates the save payload.

Run the frontend test command that works in this sandbox:

```powershell
npx vitest run --config vitest.config.ts --configLoader native --pool threads
```

Also run:

```powershell
npm run build
npm run lint:css
```

## Scope

This change does not add broker import, CSV import, real-time portfolio sync, order execution, or server-side schema changes.
