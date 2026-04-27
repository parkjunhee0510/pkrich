# UI/UX Command Desk Redesign Design

Date: 2026-04-27

## Summary

Redesign the web dashboard around a mixed PM/trader cockpit. The first screen should answer "What needs action today?" before showing the full watchlist or deep research surfaces.

The selected direction is `Daily Command Queue` with `cozy.css` tokens plus explicit new cozy premium components. The redesign stays inside the frontend UI layer and does not change pipeline data contracts, output JSON schemas, decision logic, collector behavior, or LLM usage.

## Goals

- Put today's action queue at the top of the dashboard.
- Separate PM review, trader setup, market context, and system health into clear workspace entry cards.
- Reuse the existing `cozy.css` visual system deliberately instead of introducing another theme.
- Keep data consumption additive and backward-compatible with existing dashboard payloads.
- Improve scan speed while preserving access to the existing watchlist, filters, sorting, and ticker detail flow.

## Non-Goals

- No backend, collector, analyzer, decision, datastore, or output schema changes.
- No new LLM calls or data fetching.
- No trading automation or real-time workflow.
- No rewrite of every page in the first implementation pass.
- No full CSS system replacement; `cozy.css` remains the active override layer.

## Approved Direction

The user selected:

- Overall redesign scope: full UI/UX redesign direction, bounded to the existing React frontend.
- Product model: mixed cockpit.
- First-screen hero: today's action queue.
- Layout option: `Daily Command Queue`.
- Styling approach: `cozy.css` tokens plus new explicit cozy premium components.

## Architecture

The redesign starts in `web/src/pages/Dashboard.tsx` and supporting components under `web/src/components/`.

`Dashboard` remains the page-level orchestrator that loads data through `useDashboardData()`. New command-desk components should receive already-loaded dashboard data as props and render presentation-only UI.

The top-level dashboard order becomes:

1. Command hero and action queue.
2. Workspace entry cards.
3. Market/PM/trader supporting panels.
4. Existing watchlist and deeper dashboard panels.

This preserves the current data layer and routing while changing the first-screen hierarchy.

## Components

### `DailyCommandQueue`

Owns the command-desk hero area and the queue list. It should show:

- as-of date or selected day
- compact market status context
- urgent/watch/no-action counts
- action queue cards
- quiet-day empty state when no priority items exist

### `CommandActionCard`

Renders one action item. Preferred fields come from `pm_view.today_priority_queue[]`:

- `priority_type`
- `ticker`
- `related_ticker`
- `today_priority_score`
- `summary`
- `reasons`
- `destination`

The card should make the next click obvious, normally linking to the relevant ticker detail, portfolio, or dashboard section.

### `CommandWorkspaceGrid`

Renders four workspace entry cards:

- `PM Review`: held-name risk, swap candidates, event exposure.
- `Trader Setups`: top setup candidates, catalysts, earnings proximity.
- `Market Context`: regime, macro narrative, sector tilt.
- `System Health`: API status, quality/cost/backtest health where available.

Each card should summarize status and provide one clear navigation or scroll target.

### `CommandEmptyState`

Renders when no priority queue or fallback items are available. It should explain that no urgent action is required and direct the user to watchlist, PM review, or system health instead of showing a generic missing-data message.

## Data Flow

The command desk uses only data already available through `useDashboardData()`.

Priority order:

1. Use `day.pm_view.today_priority_queue[]` when present.
2. If empty or unavailable, derive fallback presentation items from existing ticker data and current trader helper outputs, such as catalyst, earnings, setup score, and prior dashboard priority card logic.
3. If no ticker data is available, show `CommandEmptyState`.

The fallback is presentation-only. It must not reinterpret or replace the official `buy` / `watch` / `avoid` decision.

## Styling

Use `cozy.css` as the visual foundation. New command-desk styles should be explicit and grouped near the bottom of `cozy.css` under a clearly named `Cozy Premium Command Desk` section.

Primary class names:

- `cozy-premium-command-desk`
- `cozy-premium-command-hero`
- `cozy-premium-action-card`
- `cozy-premium-workspace-grid`
- `cozy-premium-workspace-card`
- `cozy-premium-command-empty`

Use existing cozy tokens:

- Surfaces: `--cozy-cream`, `--cozy-paper`, `--cozy-paper-2`
- Text: `--cozy-ink`, `--cozy-ink-soft`, `--cozy-muted`
- Accent: `--cozy-gold`, `--cozy-gold-2`, `--cozy-gold-soft`
- Status: `--cozy-good`, `--cozy-warn`, `--cozy-bad`
- Shape/shadow: `--radius-card`, `--radius-pill`, `--shadow`, `--shadow-lg`

The tone should be "morning investment briefing desk": warm and readable, but still precise enough for daily decision-making.

## Responsive Behavior

Desktop:

- Hero uses a two-column layout: queue summary/action list plus context snapshot.
- Workspace cards use a four-card grid or two-by-two grid depending on available width.
- Existing search/filter/sort controls remain accessible below the hero as a sticky quick bar.

Tablet:

- Hero collapses to one primary queue column plus compact context chips.
- Workspace cards use two columns.

Mobile:

- Hero, action cards, and workspace cards become single-column.
- Cards prioritize short summaries and keep long reasons behind expandable details.
- Sticky controls must not cover content or consume excessive vertical space.

## Error And Empty States

- Missing `pm_view`: render fallback queue from existing ticker data.
- Empty `today_priority_queue`: render fallback queue if ticker signals produce actionable items.
- Empty fallback: render `CommandEmptyState`.
- Missing system health data: show the `System Health` workspace card in a muted unavailable state.
- Data load errors continue to use the existing dashboard error handling.

No missing optional section should break the whole dashboard.

## Testing

Implementation should be verified with:

- `npm run build` from `web/`
- browser check of `/` on desktop width
- browser check of `/` on mobile width
- case where `pm_view.today_priority_queue[]` exists
- case where the queue is empty and fallback/empty state is shown

Backend tests are not required because this design does not change backend behavior or JSON contracts.

## Documentation Impact

Because this changes frontend presentation and output consumption only, implementation should update frontend-relevant documentation if behavior or routing changes. `docs/output.md` only needs updates if the frontend starts depending on new output fields, which this design intentionally avoids.

## Self-Review

- Placeholder scan: no TBD or TODO items remain.
- Consistency check: the architecture, component list, data flow, and non-goals all preserve existing data contracts.
- Scope check: this is a single frontend redesign phase centered on the dashboard first screen, not a full app rewrite.
- Ambiguity check: the selected visual direction and data fallback order are explicit.
