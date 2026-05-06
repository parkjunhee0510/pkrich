# Today Decision Strip And Data Quality Badge Design

## Status

Approved for spec review on 2026-05-06.

## Context

The Web dashboard has become the daily working surface for the stock research pipeline. It now includes:

- a dashboard header and quick filters
- action change feed
- today setup cards
- earnings and catalyst boards
- market mood and macro sections
- watchlist cards
- linked ticker detail, portfolio, signals, backtest, API, and admin pages

The current site is useful as an internal daily research tool, but the first screen still asks the user to scan several sections before answering two basic questions:

1. What should I look at first today?
2. How much should I trust the data behind that judgment?

This design adds a compact top-of-dashboard decision strip that shows at most five high-priority daily items, each paired with a data quality badge. The goal is to improve product polish and daily decision speed without adding new LLM calls or backend contracts in the first phase.

## Goals

- Surface the top five daily decision items immediately after the dashboard quick bar.
- Combine action priority and data quality in the same card.
- Reuse existing dashboard data and the existing action change feed derivation where possible.
- Make low-quality or unknown-quality data visible so the user does not overtrust a strong-looking action.
- Keep the strip compact and clearly separate from the full Action Change Feed below it.
- Preserve the existing pipeline output schema in this phase.

## Non-Goals

- No new pipeline stage.
- No new LLM inference.
- No schema version bump.
- No trading automation or real-time alerting.
- No large redesign of the dashboard.
- No replacement for the Action Change Feed; the strip is a summary, while the feed remains the fuller change log.
- No invented data quality metrics when source fields are absent.

## Accepted Approach

Use a frontend-derived Today Decision Strip.

The dashboard will derive a compact list from the currently selected day, the previous valid day, and existing ticker decision metadata. The strip will appear below the refresh note and above the Action Change Feed:

```text
Dashboard Header
Dashboard Quick Bar
Refresh Note
Today Decision Strip
Action Change Feed
Today Setup Board
Accordions
Watchlist
```

The strip displays a maximum of five cards. The full Action Change Feed remains below the strip and keeps showing a broader set of changes.

## Data Sources

The first phase uses existing frontend data only:

- `DailyEntry`
- `TickerAnalysisData`
- `TickerDecisionData`
- `TickerDecisionData.confidence_meta`
- `buildActionChangeFeed(currentDay, previousDay)`

Primary fields:

- `ticker`
- `name`
- `data_snapshot.Sector`
- `decision.action`
- `decision.conviction`
- `decision.raw_conviction`
- `decision.reason`
- `decision.confidence_meta.data_quality_score`
- `decision.confidence_meta.confidence_penalty`
- `decision.confidence_meta.evidence_coverage`
- `decision.confidence_meta.evidence_consistency`
- `decision.confidence_meta.data_quality_gate`
- action change feed entry type, tone, labels, conviction delta, and added risks

If confidence metadata is missing, the UI must show `unknown` rather than pretending the data quality is known.

## Card Types

### `quality_gate`

Highest priority. Used when confidence metadata indicates a quality gate concern.

Examples:

```text
Quality gate · FLNC max WATCH · low coverage
Quality gate · BUY capped · quality 0.52
```

Detection rules:

- `decision.confidence_meta.data_quality_gate.would_cap_action === true`
- or `decision.confidence_meta.data_quality_score < 0.6`
- or `decision.confidence_meta.confidence_penalty < 0`

### `action_change`

Used for official action changes from the previous valid day.

Examples:

```text
Top action · ALAB WATCH -> BUY · high quality
Risk alert · CAT BUY -> WATCH · low quality
```

Source:

- existing `ActionChangeFeedEntry` with `type === 'action_change'`

### `conviction_move`

Used for large conviction changes.

Examples:

```text
Conviction move · XOM -13p · watch quality
Conviction move · NVDA +20p · high quality
```

Source:

- existing `ActionChangeFeedEntry` with `type === 'conviction_change'`

### `risk_added`

Used when newly added risks are the most important visible change.

Examples:

```text
New risk · COHR · AI demand sensitivity
```

Source:

- existing feed entries with added risk count
- risk-only entries from the existing feed

### `new_ticker`

Used for newly added tickers that do not already rank higher as action or quality items.

Examples:

```text
New ticker · MOD · WATCH
New ticker · ALAB · BUY
```

Source:

- existing `ActionChangeFeedEntry` with `type === 'new_ticker'`

## Ranking Rules

The strip must show at most five cards.

Ranking priority:

1. `quality_gate`
2. action changes involving `BUY` or `AVOID`
3. other action changes
4. conviction changes with absolute delta at least 10
5. newly added risks
6. new tickers
7. lower data quality score first when the item is quality-related
8. larger absolute conviction delta first
9. higher current conviction first
10. ticker ascending

Duplicate ticker handling:

- A ticker should appear only once in the strip.
- If multiple signals exist for a ticker, keep the highest-ranked item.
- Supporting facts such as new risk count or conviction delta can be included in the chosen card.

## Data Quality Badge

Each strip card includes one compact data quality badge.

### Badge Labels

Use these labels:

- `high quality`
- `watch quality`
- `low quality`
- `unknown`

The first phase does not claim exact freshness because the current frontend data does not expose a reliable per-ticker freshness timestamp. If a future output contract adds freshness, it can be added as a separate freshness chip rather than overloading the quality badge.

### Badge Classification

Recommended classification:

```text
score >= 0.8                 -> high quality
0.6 <= score < 0.8           -> watch quality
score < 0.6                  -> low quality
missing score and no signals -> unknown
```

Additional modifiers:

- If `data_quality_gate.would_cap_action` is true, show a quality gate note.
- If `confidence_penalty` is negative, show the penalty in the supporting line.
- If `evidence_coverage` or `evidence_consistency` exists, show the weaker of the two as supporting evidence.

### Visual Tone

- `high quality`: positive or neutral-positive
- `watch quality`: caution
- `low quality`: negative/caution
- `unknown`: neutral

The class names must avoid the substring `tone-` to prevent conflicts with existing broad CSS selectors. Use scoped names such as `today-decision-quality-low` or `today-decision-stance-caution`.

## UI Content

Each card should include:

- category label such as `Top action`, `Risk alert`, `Quality gate`, `New risk`, or `Conviction move`
- ticker link to `/ticker/<TICKER>`
- short title
- one supporting line
- data quality badge
- optional compact metric such as `quality 0.58`, `-9p`, or `cap to WATCH`

Example card:

```text
Risk alert
CAT BUY -> WATCH
Conviction 72 -> 63 (-9p)
low quality · quality 0.58
```

Text must be compact and should wrap without expanding cards into oversized pill shapes.

## Empty States

If there are no decision strip items:

```text
오늘 우선 확인할 판단 변화가 없습니다.
```

If there is no previous valid day, quality-gate items from the current day may still be shown. The card copy should avoid saying "change" when there is no comparison day.

## Component Boundary

Expected implementation files:

- `web/src/utils/todayDecisionStrip.ts`
- `web/src/utils/todayDecisionStrip.test.ts`
- `web/src/components/TodayDecisionStrip.tsx`
- `web/src/components/TodayDecisionStrip.test.tsx`
- `web/src/pages/Dashboard.tsx`
- `web/src/styles/parts/dashboard.css`
- optional dashboard integration test if the placement or filter behavior needs coverage

The utility should be pure and framework-independent. The component should be presentational and receive a derived strip result as props.

## Dashboard Integration Rules

- Derive strip entries from unfiltered `day.tickers`.
- Search, sector, and trader filters must not hide the strip.
- Date selection should recompute the strip.
- The strip should render above the Action Change Feed.
- Clicking a ticker navigates to the ticker detail page.

## Styling Rules

- Use scoped `today-decision-*` classes.
- Avoid class names containing `tone-`.
- Avoid broad selectors that affect existing dashboard cards.
- Use compact cards with stable min widths and wrapping text.
- Support mobile with one-column layout below the existing mobile breakpoint.
- Keep the strip visually lighter than the watchlist cards so it reads as a summary row.

## Testing

Unit tests:

- ranks quality-gate items above action changes
- caps output at five cards
- deduplicates tickers by highest-ranked item
- classifies quality badges from score and missing metadata
- uses `unknown` when metadata is absent
- preserves action change and conviction change labels from the feed where appropriate

Component tests:

- renders up to five cards
- renders data quality badges
- links ticker symbols to ticker detail pages
- renders the empty state
- avoids `tone-` class names on card and badge elements

Dashboard integration tests:

- strip remains visible when watchlist filters hide all table rows
- strip compares the selected day with the previous valid day through the existing feed path
- strip appears before the Action Change Feed

Validation commands:

```powershell
cd web
npx vitest run --config vitest.config.ts --configLoader native --pool threads src/utils/todayDecisionStrip.test.ts src/components/TodayDecisionStrip.test.tsx src/pages/DashboardTodayDecisionStrip.test.tsx
node .\node_modules\typescript\bin\tsc -p tsconfig.app.json --noEmit --pretty false
npm run build
npm run lint:css
```

## Rollout

Implement behind normal dashboard rendering with no feature flag. If the derived strip is empty, render the compact empty state instead of hiding the section. This keeps layout behavior explicit and makes missing data visible during development.

## Risks

- Existing data may not always include `confidence_meta`; the design handles this with `unknown`.
- Data quality score naming may evolve; the utility should centralize field reading so future schema changes are localized.
- The dashboard CSS has broad global selectors; scoped class names and tests must prevent repeat visual collisions.
- Too many summary cards could reintroduce dashboard clutter; the hard cap of five prevents this.

## Acceptance Criteria

- Dashboard shows at most five prioritized decision strip cards above the Action Change Feed.
- Each card includes a data quality badge.
- Missing quality metadata displays as `unknown`.
- Strip entries are not affected by watchlist filters.
- CSS does not use `tone-` class names for the new card or badge state.
- Focused tests, TypeScript, and build pass.
