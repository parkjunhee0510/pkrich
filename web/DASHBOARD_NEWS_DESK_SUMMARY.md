# Dashboard News Desk Summary

Date: 2026-05-28

## What Changed

- Added a Dashboard news desk view model in `web/src/utils/newsDesk.ts`.
- Added `DashboardNewsDesk` to present today's situation, real-asset moves, ranked feed items, affected sectors, and affected tickers.
- Wired the news desk into `Dashboard.tsx` above the existing priority queue and detailed sections.
- Kept existing Dashboard filters, watchlist table, decision strip, action change feed, risk intel panel, setup boards, and market mood accordion.
- Added square news desk styles and CSS guard coverage to prevent pill-shaped or semicircular information DIVs.
- Added loading and route fallback regression tests so long table skeletons do not return during page navigation.
- Kept the More menu portal/z-index, viewport containment, and keyboard navigation covered by tests.
- Hardened macro-event feed rendering for generated output that provides `event_type` and `summary_ko` without `label` or `type`.
- Hardened news desk ID generation so missing generated identity fields fall back to a safe square-card item instead of crashing.
- Added a real generated-output Dashboard render regression test to prevent blank-screen regressions.

## Existing Contracts Preserved

- Existing API interfaces were not changed.
- Existing generated output schemas were not changed.
- Existing investment decision and scoring business logic were not changed.
- No external news fetch was added.

## Verification

- `npm run lint`: passed
- `npm run build`: passed
- `npm run test`: passed
- `npm run test -- src/pages/DashboardRealDataRender.test.tsx src/utils/newsDesk.test.ts`: passed
- `npm run audit:ui`: passed
- `npm run audit:performance`: passed
- Browser QA: blocked by browser security policy for the local Vite URL; covered by focused React, CSS, UI audit, and performance audit checks.

## Remaining Risks

- Real-asset fields may be absent in older generated output; the UI falls back to partial-data and empty states.
- Some non-Dashboard legacy CSS may still contain rounded shapes outside this task's scope.
- Perceived navigation speed still depends on route chunk loading and browser cache, but the Dashboard avoids reintroducing long table skeleton exposure.
- Git staging and commits are currently blocked because `.git/index.lock` cannot be created in this OneDrive worktree.
- Manual browser QA remains unverified because the browser automation policy blocked access to the local dev server URL.
