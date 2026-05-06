# Web Dashboard Action Change Feed Design

## Status

Approved for planning on 2026-05-06.

## Context

The dashboard currently loads a merged timeline from `web/src/data/StaticJsonRepository.ts`:

- `output/data/index.json` provides the latest dashboard day.
- `output/data/dashboard_history.json` provides prior dashboard days.
- The repository merges the latest index day into the history list and filters empty fallback days.

The user wants the main dashboard to surface the most valuable day-over-day changes before the watchlist cards:

- Yesterday `WATCH` -> today `BUY`.
- Yesterday `BUY` -> today `WATCH`.
- Conviction changes such as `+20`.
- Newly added risks.

Current sampled data already supports this comparison without new data collection. For example, the latest available day `2026-05-01` can be compared with `2026-04-29`, producing examples such as `CAT buy -> watch`, `XOM conviction -13`, and newly added candidate tickers.

## Goals

- Add a high-signal action change feed to the Web dashboard.
- Compare the currently selected dashboard date with the previous valid dashboard date.
- Show changes across the full watchlist, independent of dashboard search, sector filters, and trader filters.
- Include action changes, large conviction changes, new tickers, and newly added risks.
- Avoid changing pipeline output schema, LLM prompts, collector behavior, or decision logic.
- Keep the UI readable on desktop and mobile.

## Non-Goals

- No backend recomputation of action changes.
- No new output JSON field in this phase.
- No schema version bump.
- No LLM calls, data fetching, or decision reinterpretation.
- No fuzzy semantic risk clustering beyond lightweight text normalization.
- No change to ticker detail thesis diff behavior.

## Accepted Approach

Use a frontend-computed feed.

The dashboard will derive feed entries from `data.days` already loaded by `useDashboardData()`. The selected day is compared to the nearest previous valid day that has ticker data. The resulting feed is rendered under the dashboard quick bar and above `TodaySetupBoard`.

This keeps the feature cheap, fast, and low-risk. It also avoids adding another output contract while still giving the user immediate visibility into what changed today.

## Data Flow

```text
useDashboardData()
-> DashboardData.days
-> selected day index
-> previous valid day before selected index
-> buildActionChangeFeed(currentDay, previousDay)
-> ActionChangeFeed component
```

The feed should use only fields that already exist on `TickerAnalysisData`:

- `ticker`
- `name`
- `decision.action`
- `decision.conviction`
- `decision.reason`
- `risks_or_watchpoints`
- `summary`
- `signal_or_takeaway`
- `data_snapshot.Sector`

## Feed Entry Types

### `action_change`

Created when both current and previous decisions exist and `decision.action` changes.

Examples:

```text
CAT buy -> watch
ALAB watch -> buy
```

### `conviction_change`

Created when action is unchanged but both decisions have numeric conviction and the absolute delta is at least 10 points.

Examples:

```text
XOM conviction -13p
NVDA conviction +20p
```

### `new_ticker`

Created when a ticker exists in the selected day but not in the previous valid day.

Examples:

```text
ALAB new buy
COHR new watch
```

### `risk_added`

Created when the selected day has one or more normalized risk strings that were not present in the previous day.

Risk-only entries are lower priority because existing generated risk text can shift often. When a ticker already has an action, conviction, or new-ticker entry, newly added risk count should be attached as a supporting badge instead of producing a second card.

## Normalization Rules

Action values are displayed with uppercase labels:

- `buy` -> `BUY`
- `watch` -> `WATCH`
- `avoid` -> `AVOID`

Risk strings are normalized only enough to reduce obvious duplicates:

- trim leading and trailing whitespace
- collapse repeated whitespace to one space
- lowercase for comparison

The implementation should not use fuzzy matching, embeddings, LLM summaries, or translated semantic matching in this phase.

## Ranking Rules

Sort feed entries by:

1. action changes
2. conviction changes
3. new tickers
4. risk-only additions
5. absolute conviction delta, descending
6. current conviction, descending
7. ticker, ascending

The component should show a compact top set first. A practical default is 8 visible entries with a "show all" toggle if more changes exist.

## UI Placement

Render the panel in `web/src/pages/Dashboard.tsx`:

```text
dashboard header
dashboard quick bar
ActionChangeFeed
TodaySetupBoard
accordion sections
WatchlistTable
```

This position makes the feed the first actionable "what changed" view after the user sees the date, filters, and account controls.

## UI Content

Each card should include:

- ticker link to `/ticker/<TICKER>`
- company name or sector context
- primary badge such as `BUY -> WATCH`, `WATCH -> BUY`, `+20p`, or `NEW BUY`
- conviction before and after when available
- added risk count when available
- one short explanation line

Explanation priority:

1. current `decision.reason`
2. first newly added risk
3. current `signal_or_takeaway`
4. current `summary`

The card should not invent financial values or explanations.

## Visual Treatment

Use the existing dashboard visual language:

- dashboard panel section spacing
- compact cards rather than a large hero
- semantic tone colors for positive, negative, caution, and neutral states
- hard borders and readable text consistent with the current dashboard theme

Suggested tone mapping:

- upgrade to `buy`: positive tone
- downgrade from `buy` or move to `avoid`: negative tone
- large positive conviction delta: positive tone
- large negative conviction delta: caution or negative tone
- new ticker: info or neutral tone
- risk-only: caution tone

The design must remain readable on mobile. Cards should wrap naturally and avoid fixed text widths that cause overflow.

## Empty States

If there is no previous valid day:

```text
직전 리포트가 없어 변화 비교를 시작할 수 없습니다.
```

If there is a previous day but no meaningful changes:

```text
오늘 공식 판단 변화는 크지 않습니다.
```

If current or previous decisions are missing for a ticker, skip action and conviction comparison for that ticker but still allow `new_ticker` and `risk_added` where meaningful.

## Implementation Boundary

Expected files:

- `web/src/utils/actionChangeFeed.ts`
- `web/src/components/ActionChangeFeed.tsx`
- `web/src/pages/Dashboard.tsx`
- `web/src/styles/parts/dashboard.css` or a scoped existing stylesheet
- focused tests under `web/src/utils/` and/or dashboard component tests

Do not modify:

- `src/collector/`
- `src/analyzer/`
- `src/decision/`
- output schema generation
- pipeline runtime routing

Documentation changes should be limited to frontend/output docs only if the implementation changes documented consumer behavior. Since no output contract changes are planned, a schema doc update is not required.

## Testing

Add focused tests for the pure feed builder:

- creates an `action_change` entry for `watch -> buy`
- creates an `action_change` entry for `buy -> watch`
- creates a `conviction_change` entry when absolute delta is at least 10
- does not create a conviction entry when delta is below threshold and no other change exists
- creates a `new_ticker` entry for a new current ticker
- attaches added risk count to higher-priority entries
- creates risk-only entries after normalization
- handles no previous day without throwing

Update or add a dashboard render test to verify:

- the action change feed panel renders when data contains changes
- the panel is independent of watchlist search/filter state where practical
- an empty state is visible when no comparison day exists

Run at least:

```powershell
cd web
npm run build
npm run lint
```

Run `npm run test` if the local Vitest environment allows it. If it fails due to environment permissions rather than test failures, report that explicitly.

## Risks And Mitigations

Risk: Generated risk text may vary daily and create too many risk-only entries.

Mitigation: rank risk-only entries last, cap visible entries, attach risk badges to stronger change types, and use only lightweight normalization.

Risk: Users may expect the feed to respect active filters.

Mitigation: make the feed explicitly full-watchlist by placement and summary copy. Filters continue to apply to the watchlist cards below.

Risk: History payload may be missing or contain only one day.

Mitigation: render a clear empty state and avoid throwing.

Risk: A selected historical date could compare against the wrong day.

Mitigation: compare against the nearest earlier valid day in `data.days`, not necessarily calendar yesterday.

Risk: The existing `thesisDiff.ts` utility appears to contain mojibake text.

Mitigation: do not reuse it for this dashboard feed. Create a small, typed utility with clean Korean display strings.

## Success Criteria

- The dashboard shows a compact "today action changes" panel above the setup board.
- Full-watchlist changes are visible even when the watchlist table is filtered.
- The feed correctly highlights action upgrades, downgrades, large conviction changes, new tickers, and newly added risks.
- No backend output schema changes are required.
- Build and lint pass, or any local environment blocker is clearly documented.
