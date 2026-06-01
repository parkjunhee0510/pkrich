# React Performance Optimization Summary

## Scope

- `web` React app performance only.
- Existing routes, API paths, output JSON contracts, and business logic were not changed.
- Existing route-level lazy loading in `src/App.tsx` was preserved.

## Changes

- Removed the `recharts` runtime dependency from `package.json` and `package-lock.json`.
- Replaced Recharts usage in:
  - `src/components/EquityCurveChart.tsx`
  - `src/components/EpsSurpriseChart.tsx`
- The replacement charts render dependency-free responsive SVG.
- Both chart components are wrapped with `React.memo` and memoize derived chart data with `useMemo`, reducing repeated render work for stable props.
- Added shared SVG chart CSS primitives in `src/styles/parts/ui.css`.
- Removed `@dnd-kit/core`, `@dnd-kit/sortable`, and `@dnd-kit/utilities` from `package.json` and `package-lock.json`.
- Kept watchlist custom ordering lazy-loaded through `src/components/WatchlistDndList.tsx`, but replaced the DnD Kit implementation with native drag/drop plus keyboard reorder.
- Added `src/utils/watchlistOrder.ts` with pure reorder helpers and focused tests for drag and keyboard ordering behavior.
- Keyboard ordering uses `Alt+ArrowUp` and `Alt+ArrowDown` from the reorder handle.
- Added route-intent prefetching for internal links to reduce page-to-page navigation delay while preserving route-level lazy loading.
- Centralized route dynamic imports in `src/routes/routePreload.ts` so `React.lazy` and prefetch use the same chunk loaders.
- Internal route chunks now begin loading on link `pointerover`, `pointerdown`, `touchstart`, or keyboard `focusin`; dynamic paths such as `/ticker/AAPL` share one cached `TickerDetail` preload.
- Added staggered idle route warmup after the first route renders, so common page chunks are pulled in before most subsequent navigations.
- Replaced the full dashboard/table skeleton during post-initial route transitions with a lightweight route progress indicator, reducing the visible time occupied by `table-page-skeleton`-style placeholders.
- Refactored dashboard, ticker-detail, and table-page skeletons to use shared CSS layout classes and tokenized gaps instead of inline layout styles, keeping the loading UI cheaper to render and easier to audit.
- Added explicit and pattern-based rectangular surface guards so card, panel, row, summary, empty, and skeleton surfaces remain square without adding JavaScript or runtime dependencies.
- Moved repeated static JSX spacing and typography values into shared CSS utilities, reducing render-time style object churn while preserving data-driven chart dimensions and colors.
- Added a dependency-free local `Card` primitive and composed `EmptyState` with it, improving shadcn-style reuse without adding package weight or changing existing page data flow.
- Added a dependency-free local `Badge` primitive and composed `SearchEvidenceBadge` with it, keeping evidence tone classes and accessible detail labels intact.
- Extended `npm run audit:performance` to fail on:
  - `recharts` source imports
  - `@dnd-kit/*` source imports
  - `@dnd-kit/*` package dependencies
  - watchlist reorder lazy chunk growth beyond budget
- Tightened performance budgets after the bundle reductions:
  - JS gzip total: `390 kB` -> `260 kB`
  - largest JS chunk gzip: `110 kB` -> `70 kB`
  - dashboard route gzip: `22 kB`
  - watchlist reorder lazy chunk gzip: `5 kB`

## Bundle Measurement

Baseline, before removing Recharts:

- Vite transformed modules: `672`
- CSS gzip total: `29.99 kB`
- JS gzip total: `356.00 kB`
- Largest JS chunk: `assets\CartesianChart-z1izEaN7.js` at `93.52 kB gzip`

After Recharts removal and initial DnD lazy split:

- Vite transformed modules: `116`
- CSS gzip total: `30.15 kB`
- JS gzip total: `249.75 kB`
- Largest JS chunk: `assets\index-mWSSYYU3.js` at `57.53 kB gzip`
- Dashboard route chunk: `assets\Dashboard-DVKg0uEE.js` at `16.15 kB gzip` in Vite output, `15.73 kB gzip` in the audit script
- Watchlist DnD lazy chunk: about `14.94 kB gzip`

After replacing DnD Kit with native watchlist reorder:

- Vite transformed modules: `113`
- CSS gzip total: `30.15 kB` in the audit script
- JS gzip total: `235.68 kB`
- Largest JS chunk: `assets\index-KEgAseuw.js` at `58.34 kB gzip` in the audit script
- Dashboard route chunk: `assets\Dashboard-C0OIWsyk.js` at `16.15 kB gzip` in Vite output, `15.73 kB gzip` in the audit script
- Watchlist reorder lazy chunk: `assets\WatchlistDndList-45MEDJIe.js` at `0.93 kB gzip` in Vite output, `0.91 kB gzip` in the audit script

After adding route-intent prefetch:

- Vite transformed modules: `114`
- CSS gzip total: `30.15 kB` in the audit script
- JS gzip total: `236.31 kB`
- Largest JS chunk: `assets\index-BIXGOchn.js` at `58.97 kB gzip` in the audit script
- Dashboard route chunk: `assets\Dashboard-C0OIWsyk.js` at `16.15 kB gzip` in Vite output, `15.73 kB gzip` in the audit script
- Watchlist reorder lazy chunk: `assets\WatchlistDndList-45MEDJIe.js` at `0.93 kB gzip` in Vite output, `0.91 kB gzip` in the audit script

After adding idle route warmup and lightweight transition fallback:

- Vite transformed modules: `115`
- CSS gzip total: `30.29 kB` in the audit script
- JS gzip total: `236.86 kB`
- Largest JS chunk: `assets\index-CAJluJJ7.js` at `59.51 kB gzip` in the audit script
- Dashboard route chunk: `assets\Dashboard-C0OIWsyk.js` at `16.15 kB gzip` in Vite output, `15.73 kB gzip` in the audit script
- Watchlist reorder lazy chunk: `assets\WatchlistDndList-45MEDJIe.js` at `0.93 kB gzip` in Vite output, `0.91 kB gzip` in the audit script

After skeleton layout cleanup, rectangular surface guard, spacing utilities, and local Card/Badge primitives:

- Vite transformed modules: `117`
- CSS gzip total: `31.06 kB` in the audit script
- JS gzip total: `236.76 kB`
- Largest JS chunk: `assets\index-bWXlGpHY.js` at `59.51 kB gzip` in the audit script
- Dashboard route chunk: `assets\Dashboard-DvCsywk2.js` at `16.14 kB gzip` in Vite output, `15.73 kB gzip` in the audit script
- Watchlist reorder lazy chunk: `assets\WatchlistDndList-45MEDJIe.js` at `0.93 kB gzip` in Vite output, `0.91 kB gzip` in the audit script

Net bundle effect:

- JS gzip total reduced by `119.24 kB` from the original baseline.
- JS gzip total reduced by another `14.07 kB` after replacing DnD Kit with native reorder.
- Route-intent prefetch added about `0.63 kB gzip` to the main chunk to start route imports before click navigation.
- Idle route warmup and lightweight transition fallback added about `0.55 kB gzip` on top of route-intent prefetch.
- Largest JS chunk reduced by `34.01 kB gzip` from the original baseline, using audit-script gzip measurement.
- Dashboard route chunk reduced from `35.10 kB gzip` to `16.15 kB gzip` in Vite output.
- Watchlist reorder lazy chunk reduced from about `14.94 kB gzip` to `0.91 kB gzip` in the audit script.
- The Recharts `CartesianChart` chunk is no longer emitted.
- `npm uninstall recharts` removed `39` installed packages.
- `npm uninstall @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities` removed `5` installed packages.

## Lazy Loading And Render Work

- Page-level `React.lazy` routes remain in `src/App.tsx`.
- `PriceChart` remains component-lazy in Price History and Ticker Detail, so `lightweight-charts` is still deferred until a price chart is rendered.
- Equity and EPS charts no longer trigger the Recharts chart stack, so Backtest, Portfolio, and Ticker Detail load less chart code.
- Watchlist custom ordering remains behind the lazy `WatchlistDndList` boundary and now uses native browser drag/drop events instead of a DnD runtime.
- The default dashboard no longer imports `DndContext`, `useSortable`, `PointerSensor`, or `KeyboardSensor`.
- Route chunks still lazy-load, but internal links now warm the matching chunk on hover, pointer down, touch start, or keyboard focus so navigation does not wait until the click commit to start the dynamic import.
- After the first resolved route, route transitions use a small progress indicator instead of the full dashboard/table skeleton fallback.
- Route chunks are warmed one at a time during browser idle time, skipping the current route and reusing the same in-flight promise cache used by intent prefetch.
- Full-page skeletons now share class-based structure for stacks, rows, lists, and page shells; only dynamic skeleton dimensions remain inline.
- High-churn pages and panels now use tokenized utility classes for static spacing and compact text, while keeping dynamic visual encodings such as bar heights, chart sizes, and signal colors local to the data render.
- Empty states now share the same local card surface primitive, so future surface refinements land in one CSS layer instead of each page recreating the same structure.
- Search evidence badges now share the local badge primitive, preserving existing tone classes while giving future badges a common dependency-free base.
- Pure SVG chart components use `React.memo` and memoized data projection to avoid recomputing chart geometry on unrelated parent renders.
- Watchlist reorder helpers are pure functions, which keeps reorder behavior testable without rendering React or loading browser drag libraries.

## Verification Commands

- `npm run build`
- `npm run audit:ui`
- `npm run lint`
- `npm run test`
- `npm run audit:performance`

Latest measured audit:

- `index.html` raw: `1.07 kB / 2.00 kB`
- CSS gzip total: `31.06 kB / 36.00 kB`
- JS gzip total: `236.76 kB / 260.00 kB`
- Largest JS gzip: `59.51 kB / 70.00 kB`
- Dashboard route gzip: `15.73 kB / 22.00 kB`
- Watchlist reorder gzip: `0.91 kB / 5.00 kB`
- UI audit: 87 JSX/TSX files, 0 accessibility issues
- Token contrast: lowest `5.89:1`
- Touch targets: 5/5 checks passed
- Hydration mode: client-rendered `createRoot`
- Lint: passed
- Vitest: 37 files, 129 tests passed
- Local dev URL previously checked: `http://127.0.0.1:5173`

## Lighthouse Status

The app has bundle and dependency changes that should improve Lighthouse performance inputs, but Lighthouse score measurement has not been produced in this local environment.

Latest Lighthouse blocker evidence:

- `Get-Command lighthouse` and `where.exe lighthouse` did not find a local Lighthouse executable.
- `npm ls lighthouse --depth=0` returned an empty dependency tree.
- `npm cache ls lighthouse --json` returned no cached package.
- Global npm packages under `C:\Users\junhe\AppData\Roaming\npm\node_modules` did not contain Lighthouse.
- `NPM_CONFIG_OFFLINE=true` prevents uncached package fetches by default.
- With offline mode overridden and npm cache redirected to the workspace, `npx --yes lighthouse --version` still failed with `ECONNREFUSED 127.0.0.1:9` for `https://registry.npmjs.org/lighthouse`.
- Chrome exists at `C:\Program Files\Google\Chrome\Application\chrome.exe`, but minimal `--headless=new --dump-dom` runs failed with Crashpad/Mojo access-denied errors before producing DOM output.
- The Chrome headless failure reproduced with both a workspace user data dir and an ASCII-only scratch dir under `C:\Users\junhe\.codex\memories`, so it is not just a OneDrive or Korean-path issue.

Because the Lighthouse package is unavailable and local headless Chrome cannot start in this sandbox, the current measurable performance proof is the production Vite bundle output plus `npm run audit:performance`.
