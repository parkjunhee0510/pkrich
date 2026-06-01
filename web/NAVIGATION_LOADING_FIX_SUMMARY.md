# Navigation Loading Fix Summary

## Scope

- Frontend navigation, loading state, menu layering, and rectangular surface cleanup.
- Existing route behavior, API paths, output JSON contracts, props, and business logic were preserved.
- No new npm dependencies were added.

## Problems Addressed

- Page-to-page navigation could spend too long showing full table/page skeletons.
- `table-page-skeleton` could be shown again on remounts even when the same data had already loaded.
- The "More" navigation menu could render under other UI layers instead of above the page.
- Some repeated card, row, summary, and menu surfaces could drift back toward pill or semi-circular shapes.

## Changes

- Added stale-while-revalidate style client caches for dashboard data, static JSON resources, local portfolio status, and live price history rows.
- Updated API Status and static Admin cost-log loading to reuse the shared JSON resource hook, so cached data is visible immediately on remount while a background refresh continues.
- Kept skeletons for true initial loading states only. When cached data exists, pages render the cached content instead of returning to full table/page skeletons.
- Rendered the "More" menu through a React portal into `document.body`.
- Positioned the "More" menu with fixed coordinates from the trigger button and kept it updated on scroll and resize.
- Added `--z-popover: 3000` and moved the dropdown to that layer so it is not buried under page content.
- Preserved outside-click closing for both the trigger wrapper and the portal menu.
- Added rectangular styling coverage for the portal menu and kept the existing square guards for card, panel, summary, row, empty, error, and skeleton surfaces.
- Ensured the menu items keep at least the shared 44px touch target.

## Regression Coverage

- Dashboard data remount uses cached payload with `loading=false`.
- Shared JSON resource remount uses cached data while revalidation is still pending.
- Local portfolio status remount avoids a full loading reset when cached.
- Price history rows remount from cache with `loading=false`.
- Layout "More" menu is portaled to `document.body`.
- Navigation layering CSS requires fixed positioning, popover z-index, square menu radius, and 44px menu item touch target.
- Summary/card shape tests cover rectangular guard selectors, including the portal menu.
- Admin performance measurement tests were updated for static cost-log loading through the JSON resource hook.

## Verification

- `npm run lint`: passed.
- `npm run test`: passed, 41 files and 134 tests.
- `npm run audit:ui`: passed, 88 JSX/TSX files with 0 accessibility issues.
- `npm run build`: passed.
- `npm run audit:performance`: passed.
- `npm run lint:css`: exit code 0, with 1049 warning-level strict-value findings still present.

## Remaining Risks

- Browser visual QA was not completed in this environment after the interrupted dev-server attempt, so the portal menu behavior is covered by tests and CSS audits but not by a fresh manual browser click-through.
- The stylelint strict-value warnings are broader token cleanup debt and were not fully resolved in this focused navigation/loading fix.
- The client caches are in-memory only; a full page reload still performs the normal initial load and may show skeletons as designed.
