# Dashboard Ticker Priority Flow Design

## Status

Approved for spec review on 2026-05-21.

## Context

The project has matured into a batch stock research system with stable daily
artifacts, a quality reliability loop, search evidence telemetry, risk
intelligence outputs, and frontend pages for dashboard, ticker detail,
portfolio, backtest, sectors, and admin review.

Recent work made the quality and reliability layer more visible:

- `quality_reliability_loop.json` reports decision quality and artifact
  reliability as operational.
- `performance_baseline.json` exposes search evidence coverage, priority
  refresh counts, and readiness telemetry.
- `search_evidence.json` now records priority refresh reasons and status
  counts.
- `risk_intel_summary.json` and related artifacts provide risk explanation
  material for frontend consumption.

The latest operating gap is not that the system lacks data. It is that the main
dashboard and ticker detail page do not yet guide the user through a single
daily PM workflow:

```text
Which tickers should I inspect first today?
Why are they important?
What should I verify in the ticker detail page?
```

The user selected a combined dashboard and ticker-detail expansion. The chosen
direction is:

- risk alerts
- opportunity detection
- a mixed daily review priority score

The visual option selected for the first slice is a "today review queue" centered
dashboard flow rather than a separate risk/opportunity two-lane layout or a
heavy ticker-preview layout.

## Goals

- Add a main-dashboard review queue that highlights the tickers most worth
  inspecting today.
- Explain why each ticker is in the queue using risk, opportunity, evidence, and
  action-context signals.
- Let the user drill from each queue row into `/ticker/:ticker`.
- Add a ticker-detail research brief that expands the same reasons shown on the
  dashboard.
- Keep all new scoring read-only and presentation-only.
- Preserve official pipeline decisions exactly as written by backend artifacts.
- Make missing or partial data clear without breaking the page.

## Non-Goals

- Do not change official `buy`, `watch`, or `avoid` decisions.
- Do not change pipeline factor weights, decision thresholds, or model routing.
- Do not create a new backend artifact in this first slice.
- Do not call search, risk, or LLM providers from frontend code.
- Do not enable search evidence gate enforcement.
- Do not introduce trade execution, automatic portfolio sizing, or order logic.
- Do not redesign the entire dashboard or ticker detail page.

## Accepted Approach

Build a frontend-only daily priority view model and use it in two places:

```text
output/data/*.json
-> frontend data hooks / repository
-> buildTodayPriorityQueue(...)
-> TodayPriorityQueue on Dashboard
-> TickerResearchBrief on TickerDetail
```

This keeps the first slice small and reversible. It uses existing generated
artifacts and does not add a new pipeline stage.

The queue score is not an investment decision. It is a display ordering score
that helps the user decide what to inspect first.

## Alternatives Considered

### A. Today Review Queue Centered Dashboard

Put a compact review queue near the top of `/`. Each row shows ticker, official
action, priority label, risk badge, opportunity badge, evidence badge, one-line
reason, and a link to ticker detail.

This is the accepted option because the daily workflow starts with prioritizing
attention.

### B. Risk And Opportunity Two-Lane Dashboard

Separate the dashboard into defensive and offensive lanes. This makes risk and
opportunity easier to compare, but it forces the user to mentally merge the two
lanes when deciding what to inspect first.

This is out of scope for this slice. It should require a separate spec if the
dashboard later needs a dedicated PM war-room view.

### C. Ticker Preview First Dashboard

Show a selected ticker preview directly in the dashboard with an abbreviated
research brief. This improves context before clicking, but it increases first
screen density and risks duplicating ticker detail content.

This is deferred until the review queue has proven useful.

## User Experience

### Dashboard

The dashboard gets a new `TodayPriorityQueue` section near the first viewport,
after high-level market or macro context and before lower-priority panels.

The section shows roughly five to eight tickers. Each item includes:

- ticker
- official action
- priority label
- risk badge
- opportunity badge
- evidence badge
- one-line reason
- destination link to `/ticker/:ticker`

Example row:

```text
AMD  BUY review  Opportunity-led review
Risk low | Opportunity high | Evidence refresh needed
Sector strength and conviction improved, but priority evidence is not refreshed.
```

The queue should be dense, readable, and work-focused. It should not become a
marketing-style hero or a large decorative card.

### Ticker Detail

The ticker detail page gets a `TickerResearchBrief` section close to the current
decision summary.

It answers:

- why this ticker is worth reviewing today
- what the key opportunity signal is
- what the key risk signal is
- whether evidence coverage is sufficient
- what the next human check should be

The detail page should reuse the same reason vocabulary as the dashboard so the
drilldown feels continuous.

## Data Inputs

The frontend should consume existing artifacts only:

- `output/data/index.json`
- `output/data/search_evidence.json`
- `output/data/risk_intel_summary.json`
- `output/data/risk_intel_graph.json` when already available through existing
  hooks
- `output/data/quality_reliability_loop.json`
- `output/data/analysis_performance.json` only if it is already exposed through
  the current frontend data repository in this implementation slice

The exact implementation should prefer the current frontend repository and hook
patterns. If an existing data hook already loads one of these artifacts, extend
it instead of creating a parallel loading path.

## View Model

Add a pure frontend helper, likely:

```text
web/src/utils/todayPriorityQueue.ts
```

The helper builds items similar to:

```ts
type TodayPriorityQueueItem = {
  ticker: string
  officialAction: string
  priorityScore: number
  priorityLabel: string
  riskLevel: 'none' | 'low' | 'medium' | 'high' | 'unknown'
  opportunityLevel: 'none' | 'low' | 'medium' | 'high' | 'unknown'
  evidenceStatus: 'covered' | 'not_refreshed' | 'stale' | 'missing' | 'unknown'
  reasons: string[]
  destination: string
}
```

The exact type names may follow the existing type style in
`web/src/types/index.ts`.

The helper must be deterministic:

- Higher risk and higher opportunity should both increase review priority.
- Evidence gaps should add review priority, especially for priority tickers.
- Official decisions from backend artifacts should not be changed.
- Same-score items should preserve the dashboard or watchlist order.
- Missing data should lower confidence in the labels, not crash the view.

## Priority Scoring

V1 scoring should be simple and explainable:

- risk alert present: meaningful positive weight
- opportunity signal present: meaningful positive weight
- priority search evidence not refreshed: positive weight
- stale or missing evidence: positive weight
- important action context such as `buy` or `avoid`: positive weight
- action change context: positive weight only when the current frontend data
  repository already exposes it

The output must expose reasons beside the score. A score without reasons is not
useful for this workflow.

The score is for sorting only. It must not be written back to official decision
objects and must not be used to recompute actions.

## Components

### TodayPriorityQueue

Suggested path:

```text
web/src/components/TodayPriorityQueue.tsx
```

Responsibilities:

- Render compact queue rows.
- Show badge groups for risk, opportunity, and evidence.
- Show an empty state when no review items exist.
- Link to ticker detail routes.
- Keep text short enough for mobile and desktop.

### TickerResearchBrief

Suggested path:

```text
web/src/components/TickerResearchBrief.tsx
```

Responsibilities:

- Render the selected ticker's review reason summary.
- Show opportunity, risk, evidence, and next-check sections.
- Fall back gracefully when the ticker is not in the daily queue.
- Avoid recomputing official decisions.

### Page Integration

Dashboard integration:

```text
web/src/pages/Dashboard.tsx
```

Ticker detail integration:

```text
web/src/pages/TickerDetail.tsx
```

Type integration:

```text
web/src/types/index.ts
```

## Empty And Error States

The UI must degrade gracefully:

- Missing `search_evidence.json`: evidence badge uses a Korean no-evidence-data
  fallback label.
- Missing risk intel artifact: risk badge uses a Korean no-risk-data fallback
  label.
- Missing quality loop artifact: hide the global quality indicator or show a
  Korean no-quality-status fallback label.
- No queue candidates: show a Korean empty-state label indicating that there are
  no special priority tickers today.
- Missing ticker-specific queue item on detail page: keep existing ticker detail
  page and show a neutral research brief fallback.
- Conflicting official action and queue label: display official action first and
  treat queue label as review context only.

## Testing Plan

Add focused frontend tests for the pure helper and components.

Priority helper tests:

- Risk plus opportunity ranks ahead of low-context names.
- `priority_refresh_reasons.not_refreshed` creates an evidence reason and badge.
- Missing search evidence and risk intel data produce safe defaults.
- Same-score items preserve input order.
- Official actions are copied through but not modified.

Component tests:

- Dashboard renders the today priority queue.
- Queue rows show risk, opportunity, evidence badges, and one-line reasons.
- Queue rows link to `/ticker/:ticker`.
- Ticker detail renders the research brief for a queue item.
- Ticker detail falls back safely when the ticker is absent from the queue.

Suggested commands:

```text
cd web && npm test -- --run
cd web && npm run build
```

If the repository uses a narrower test command for specific frontend tests, use
that command first and then run the build.

## Documentation Updates

If implemented, update:

- `docs/ui-ux-structure.md` for dashboard and ticker detail structure.
- `docs/output.md` only if frontend artifact consumption contracts are changed.

No backend layer documentation is required unless implementation changes backend
output shape or generation timing.

## Completion Criteria

- Dashboard includes a review queue for daily ticker inspection.
- Ticker detail includes a research brief connected to the same queue reasons.
- The queue is read-only and does not alter official decisions.
- Missing artifacts produce clear fallback states.
- Frontend tests cover priority helper behavior and main rendering paths.
- Frontend build passes.
