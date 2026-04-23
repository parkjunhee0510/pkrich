# Web Committee UI Design

## Goal

Surface the new `committee_analysis` payload in the web app so users can always see the committee debate alongside the existing rule-based decision output.

The UI must make this distinction explicit:

* `decision` is the official execution-oriented output
* `committee_analysis` is the always-visible debate and synthesis layer

## Scope

In scope:

* Dashboard watchlist UI
* Ticker detail UI
* Web type definitions for `committee_analysis`
* Safe fallbacks for missing or partial committee payloads

Out of scope:

* New pages or routes
* New sorting or filtering rules based on committee output
* Any change to rule-based decision semantics
* Any backend schema redesign beyond the already-added additive payload

## Existing Context

The backend now writes `committee_analysis` into each ticker payload in dashboard and ticker JSON outputs.

The web app already consumes:

* dashboard ticker payloads through `useDashboardData`
* ticker detail payloads through `useTickerAnalysis` and dashboard fallback

This means no new fetch path is required. The work is a presentation-layer extension only.

## Approach Options

### Option 1: Inline Rendering In Existing Files

Render committee UI directly inside `WatchlistTable.tsx` and `TickerDetail.tsx` with minimal helper functions.

Pros:

* Fastest to implement
* Lowest file count

Cons:

* Presentation logic gets duplicated across dashboard and detail views
* Harder to evolve once committee UI grows

### Option 2: Small Shared Committee Components

Add small dedicated committee UI components and reuse them in dashboard and ticker detail.

Pros:

* Clear boundary for committee presentation
* Shared rendering and fallback logic
* Easier to evolve later

Cons:

* Slightly more upfront structure

### Recommendation

Use Option 2.

The existing web app already uses meaning-based UI components such as `DecisionCard` and `TraderDecisionBoard`. Committee UI fits that pattern better as a small shared presentation slice rather than scattered inline markup.

## UI Design

## Dashboard

Each watchlist card gets a separate committee strip near the bottom of the card, visually distinct from the official decision badge and conviction area.

The dashboard committee strip shows:

* agreement status
* deep review status
* deep review reason codes when present
* role summaries for `growth_analyst`, `value_skeptic`, `risk_manager`, `macro_strategist`
* PM conclusion

Design rules:

* The strip is secondary to the official decision badge
* Role summaries stay compact and scan-friendly
* PM summary is visually strongest within the strip
* Missing committee payload should show a minimal fallback state rather than collapsing the card

The selected placement is a separate committee strip instead of embedding committee content into the main watchlist stat grid.

## Ticker Detail

Add a new `위원회` tab to ticker detail.

That tab contains:

* a top PM conclusion card
* a metadata row for agreement status, deep review state, and deep review reasons
* accordion sections for `growth_analyst`, `value_skeptic`, `risk_manager`, and `macro_strategist`

Design rules:

* PM synthesis appears first and stays fixed at the top of the tab
* Supporting roles live below in expandable sections
* Invalid or missing role payloads render safe fallback copy rather than blank regions
* The detail tab should read like “final debate record”, not like a replacement decision engine

The selected placement is a dedicated committee tab rather than mixing committee content into existing overview sections.

## Data Model

Add web types that mirror the additive backend payload shape.

### CommitteeAnalysisData

Fields:

* `status`
* `agreement_status`
* `deep_review_triggered`
* `deep_review_reasons`
* `roles`

### CommitteeRoleData

Fields:

* `role`
* `round`
* `profile`
* `stance`
* `action`
* `confidence`
* `strong_objection`
* `summary`
* `valid`
* `invalid_reason`

The web types should remain permissive enough to tolerate additive schema growth, but strict enough to avoid `any`-style leakage through the component layer.

## Component Plan

Recommended new shared components:

* `CommitteeBadgeRow`
  Shows agreement status, deep review flag, and reason badges

* `CommitteeSummaryStrip`
  Dashboard watchlist card committee presentation

* `CommitteeDetailPanel`
  Ticker detail committee tab content

Responsibilities:

* shared fallback behavior lives inside committee components, not spread through pages
* pages pass raw `committee_analysis` payloads and let the shared components normalize display behavior

## Rendering Rules

### Dashboard Rules

* If `committee_analysis` is absent, render a minimal `committee unavailable` fallback
* If a role summary exists, show it in compact one-line form
* If `deep_review_triggered` is true, show a visible but secondary badge
* Do not alter card ordering, scoring, or action logic

### Detail Rules

* If PM summary exists, it leads the tab
* If role payload is invalid, show a concise fallback such as `committee output invalid`
* If `deep_review_reasons` is empty, omit the reason list instead of rendering empty chrome
* Keep all committee visuals clearly separate from the existing `DecisionCard`

## Styling Direction

Stay within the existing visual language already used in the dashboard and ticker detail pages.

Specific guidance:

* reuse existing card, badge, and section-shell idioms
* avoid creating a totally different visual system for committee UI
* keep the committee strip and tab legible in both dense dashboard scanning and mobile detail layouts
* prefer additive styles in existing CSS files unless a new component-specific grouping clearly improves maintainability

## Error Handling And Fallbacks

The UI must not assume the committee payload is fully populated.

Required fallback cases:

* no `committee_analysis`
* missing `roles`
* missing PM payload
* role payload present but marked invalid
* deep review enabled but no readable reason text

Fallback behavior should preserve layout stability. The UI should degrade to simple labels and short placeholders rather than disappearing or throwing.

## Verification

Preferred verification:

* front-end tests for normal payload and fallback rendering if the repo already supports practical component-level tests
* `npm run build` as the minimum required verification

At minimum verify these states:

* full committee payload renders in dashboard strip
* missing committee payload renders safely in dashboard strip
* committee tab renders in ticker detail
* PM-led layout appears above role accordions
* official decision UI remains unchanged in meaning and placement

## Implementation Boundaries

Primary files expected to change:

* `web/src/types/index.ts`
* `web/src/components/WatchlistTable.tsx`
* `web/src/pages/TickerDetail.tsx`
* shared committee UI components under `web/src/components/`
* existing CSS files used by dashboard and ticker detail

Secondary documentation updates may be needed if the web output contract description is kept in repo docs.

## Suggested Build Order

1. Add committee types to the web layer
2. Create shared committee UI components
3. Wire the dashboard committee strip into watchlist cards
4. Add the committee tab to ticker detail
5. Add or update focused UI tests if practical
6. Run front-end verification

## Self-Review

Placeholder scan:

* No `TODO` or `TBD` placeholders remain

Internal consistency:

* Dashboard uses a separate strip
* Ticker detail uses a dedicated committee tab
* Both preserve `decision` as the primary official output

Scope check:

* This is focused enough for a single implementation plan
* It does not attempt to redesign unrelated dashboard behavior

Ambiguity check:

* The role presentation hierarchy is explicit: PM first in detail, all roles visible in dashboard strip
* Committee UI is presentation-only and must not change decision semantics
