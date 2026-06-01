# UI Modernization Summary

## Scope

- `web` UI only. Existing API interfaces, data contracts, and business logic were not changed.
- The current `web` app does not include Tailwind or shadcn CLI configuration files, so no Tailwind-related setup was removed or replaced. To keep bundle growth small and avoid new dependencies, shadcn/ui-style primitives were implemented locally with CSS variables.

## Component Structure

- Added dependency-free UI primitives:
  - `src/components/ui/Badge.tsx`
  - `src/components/ui/Button.tsx`
  - `src/components/ui/Card.tsx`
  - `src/components/ui/EmptyState.tsx`
  - `src/lib/utils.ts`
  - `src/lib/rovingTabs.ts`
  - `src/styles/parts/ui.css`
- Reused the new primitives for error and empty states across Dashboard, Portfolio, Calendar, Signals, and Ticker Detail flows.
- Composed `EmptyState` on top of the local shadcn-style `Card` primitive without changing the existing `EmptyState` API.
- Composed `SearchEvidenceBadge` on top of the local shadcn-style `Badge` primitive while preserving its existing accessible detail label, `title`, and evidence tone classes.
- Extracted roving tab keyboard math into a tested shared helper so future tablists can reuse the same Arrow/Home/End behavior.
- Refactored `DashboardSkeleton`, `TickerDetailSkeleton`, and `TablePageSkeleton` to use shared class-based skeleton layout primitives instead of inline spacing/layout styles.
- Replaced repeated static inline spacing and typography styles in Admin, Signals, Scenario, Chat, Backtest, Portfolio, and analytics panels with shared utility classes.
- Kept existing page data flow and route behavior intact.

## Visual System

- Consolidated semantic design tokens in `src/styles/parts/tokens.css`:
  - shadcn-compatible surface, text, border, ring, primary, secondary, accent, destructive, and muted tokens.
  - 8px-oriented radii and reusable font-size, timing, easing, and touch-target tokens.
  - `prefers-color-scheme: dark` overrides for dark-mode contrast.
- Added `color-scheme: light dark` so native form controls and scrollbars can follow the OS theme.
- Preserved the existing CSS cascade structure and added `ui.css` as the final primitive override layer.
- Removed render-blocking Google Font imports and `index.html` font preconnect/stylesheet tags, then switched to local system font stacks.
- Added light/dark `theme-color` metadata to keep mobile browser chrome aligned with the active color scheme.
- Removed duplicate global scrollbar CSS and replaced `background-attachment: fixed` with a scroll-friendly background for better mobile performance.
- Aligned `--muted` with the shadcn semantic surface token and moved existing neutral accent usage to `--cozy-muted` to preserve legacy visuals while keeping token contrast valid.
- Added a final rectangular surface guard for repeated card, summary, priority-row, empty, error, chart, panel, and skeleton surfaces so these UI blocks render as square `div`-like containers instead of semi-circular or pill-shaped cards.
- Added a broader pattern guard for future `div`-like `*-card`, `*-panel`, `*-surface`, `*-summary`, `*-empty`, and `*-row` classes so newly added information blocks default to square containers without needing one-off selector patches.
- Added square `ui-card`, `ui-card-header`, `ui-card-title`, `ui-card-description`, `ui-card-content`, and `ui-card-footer` primitives to align reusable surfaces with the local shadcn token layer.
- Added square `ui-badge` primitives with default, secondary, outline, destructive, and unstyled variants so compact metadata can migrate without losing existing tone-specific classes.
- Added spacing and typography utility classes for common top/bottom gaps, compact inline clusters, small text, muted metadata, and price deltas so repeated layouts use design tokens instead of ad hoc inline values.

## Accessibility And Mobile

- Added accessible loading semantics:
  - skeleton wrappers now use `role="status"`, `aria-busy`, and screen-reader labels.
  - skeleton blocks are marked `aria-hidden`.
  - skeleton layout spacing now comes from CSS tokens, keeping responsive sizing consistent and reducing hydration-sensitive inline style churn.
- Improved error states:
  - `role="alert"`, assertive live region, clearer retry button label, and stronger contrast.
- Improved empty states:
  - consistent reusable empty-state layout with mobile wrapping and dark-mode support.
- Improved navigation:
  - primary nav has `aria-label`.
  - hamburger and more menu use `aria-controls`, `aria-expanded`, and explicit labels.
  - client-only date rendering avoids hydration mismatch from direct render-time `new Date()`.
- Added missing labels and pressed states:
  - dashboard, calendar, signals, price history, ticker detail, scenario, and chat controls.
  - account preset, sort, trader filter, density, and portfolio mode buttons.
  - portfolio ticker picker and delete buttons.
- Converted info tooltip triggers to real `button` controls with `type`, `aria-label`, `aria-describedby`, keyboard focus visibility, and a 44px hit area while preserving the compact visual mark.
- Made watchlist cards keyboard-activatable links with `role="link"`, `tabIndex`, `aria-label`, and Enter/Space handling while preserving the existing whole-card click navigation.
- Connected ticker detail tabs and filing tabs to their active tabpanels with stable `id`, `aria-controls`, and `aria-labelledby` relationships.
- Added roving `tabIndex` and Arrow/Home/End keyboard navigation to Ticker Detail tablists that contain real `role="tab"` buttons.
- Added `aria-sort` to Price History sortable column headers so assistive tech can announce the active sort state.
- Added a shared `--touch-target: 44px` token and applied it to common interactive controls.
- Added mobile text hygiene defaults:
  - `text-size-adjust: 100%` / `-webkit-text-size-adjust: 100%` on the root document.
  - inherited typography and color for native form controls.
  - body-copy overflow wrapping for long Korean/URL-like text without horizontal page spill.
- Removed remaining negative letter-spacing declarations from the UI CSS layers.

## Performance And Bundle

- No new npm dependencies were added.
- External font network requests were removed.
- Vite lazy-route splitting remains unchanged.
- Added `npm run audit:ui`, a dependency-free source audit for JSX control labels, button types, tab/tabpanel linkage, roving tab focus, sortable table header state, native dark-mode browser chrome, non-native keyboard interaction, forbidden UI/CSS patterns, semantic token contrast, 44px touch-target coverage, mobile text hygiene, CSS imports, and client-render hydration mode.
- Added `npm run audit:performance`, a dependency-free dist audit that blocks external font regressions and checks gzip budgets for `index.html`, CSS, total JS, and the largest JS chunk.
- Production build completed successfully. Current CSS output is `dist/assets/index-BMrMWPHX.css` at `201.11 kB` / `31.80 kB gzip`; the added primitive layer, spacing utilities, and rectangular guards remain inside the CSS budget.

## Verification

- `npm run lint` passed with exit code 0.
- `npm run lint:css` passed with exit code 0 after fixing blocking CSS errors; the stylesheet still reports existing strict-value warnings.
- `npm run test -- --run` passed with exit code 0: 37 files, 129 tests.
- `npm run build` passed with exit code 0.
- `npm run audit:ui` passed with exit code 0:
  - JSX accessibility: 87 files, 0 issues
  - forbidden UI patterns: 0 issues
  - dark-mode browser chrome: 3/3 checks
  - token contrast: lowest checked pair `5.89:1`
  - touch targets: 5/5 checks
  - mobile text hygiene: 3/3 checks
  - CSS imports: 14 imports, all present
  - hydration mode: client-rendered `createRoot`
- `npm run audit:performance` passed with exit code 0:
  - `index.html` raw: `1.07 kB` / `2.00 kB`
  - CSS gzip total: `31.06 kB` / `36.00 kB`
  - JS gzip total: `236.76 kB` / `260.00 kB`
  - largest JS gzip: `assets\index-bWXlGpHY.js` at `59.51 kB` / `70.00 kB`
  - Dashboard route gzip: `15.73 kB` / `22.00 kB`
  - Watchlist reorder gzip: `0.91 kB` / `5.00 kB`
- Static accessibility scan for JSX controls found 0 issues across 87 TSX/JSX files: no buttons without `type`, no unnamed buttons, and no unlabeled input/select/textarea controls.
- Semantic color token contrast checks passed WCAG AA for light and dark foreground/surface, primary, secondary, muted, accent, and destructive pairs. The lowest checked ratio is light destructive text/background at 5.89:1.
- Source scan found no `fonts.googleapis`, `fonts.gstatic`, CSS `@import url`, `background-attachment: fixed`, negative `letter-spacing`, or placeholder `No data available` strings in `src` or `index.html`.
- Regression tests now cover skeleton layout primitives plus both explicit and pattern-based rectangular surface guards so `table-page-skeleton`, summary cards, priority rows, empty states, error states, and future div-like card/panel rows do not drift back to pill or semi-circle shapes.
- Regression tests now also cover selected high-churn frontend files so static `margin`, `padding`, `display`, `gap`, and `fontSize` values stay in shared CSS rather than JSX inline styles. Dynamic chart dimensions, bar heights, and data-driven colors remain inline where needed.
- Regression tests cover the new `Card` primitive and confirm `EmptyState` uses it while preserving the current props.
- Regression tests cover the new `Badge` primitive and confirm `SearchEvidenceBadge` uses it while preserving evidence tone, aria-label, and title behavior.

## Notes

- Vitest now runs with `--configLoader native --pool threads --maxWorkers 1` so the Windows workspace can execute the suite without fork-worker `spawn EPERM` failures.
- The analysis performance panel keeps the same visible content, but duplicate return values now carry contextual accessible labels so tests and assistive tech can distinguish repeated metrics.
- Chrome/Edge headless screenshot capture was attempted for desktop and mobile viewports, but the local Windows sandbox denied Chromium Crashpad/Mojo startup. Browser visual QA remains the one runtime check that could not be completed in this environment.
- Lighthouse CLI is not present in dependencies or npm cache in this restricted environment, so Lighthouse score measurement could not be run locally. The performance-oriented changes that were verified are removal of external font requests, route lazy loading preservation, dependency-free UI primitives, and production bundle output tracking.
