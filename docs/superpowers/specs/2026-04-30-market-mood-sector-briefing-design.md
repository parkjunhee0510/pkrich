# Market Mood Sector Briefing Design

## Purpose

Improve the dashboard section currently titled "오늘 시장 분위기" so users can read a connected market view instead of separate widgets. The section should answer three questions in order:

1. What is today's market mood?
2. Which sectors deserve attention or caution under that mood?
3. Which tickers connect to those sectors?

The approved direction is a compact briefing that shows both "주목 섹터" and "주의 섹터" at the top, with a smaller full-sector comparison beneath it.

## Current Context

The dashboard currently renders the market mood section in `web/src/pages/Dashboard.tsx` using these pieces:

- `MarketRegimeBanner`
- `MacroNarrativePanel`
- `MacroContextBar`
- `MarketOverview`
- `SectorSummary`

These components show useful information, but the user has to mentally connect regime, macro context, sector performance, and tickers. The new design makes that connection explicit while preserving the existing dashboard accordion.

The output contract should remain stable for the initial implementation. The frontend should derive the new briefing from the existing dashboard payload rather than requiring a new LLM call, data collection step, or JSON schema migration.

## Approved Approach

Use the recommended hybrid approach:

- A top-level connected briefing for fast judgment.
- Two side-by-side lanes: "주목 섹터" and "주의 섹터".
- Sector rows that include the sector name, fit badge, average daily change, short rationale, and related ticker chips.
- A lower full-sector comparison table for users who want more detail.
- A macro evidence panel that keeps the reasoning visible without dominating the first scan.

The rejected alternatives were:

- A full matrix first, which is useful for analysis but weaker for fast reading.
- A ticker-first feed, which is actionable but overlaps with recommendation surfaces and hides the sector-level reasoning.

## User Experience

The "오늘 시장 분위기" accordion summary should become more informative. Instead of only showing the regime and a generic macro/sector phrase, it should include the regime plus the count of focus and watch sectors when available. Example:

`Risk-on · 주목 2개 / 주의 2개 · 매크로와 섹터 흐름`

Inside the expanded section, the visual order should be:

1. Market regime summary: regime, confidence, implication, and key drivers.
2. Sector briefing lanes: focus sectors and watch sectors presented side by side on desktop and stacked on mobile.
3. Full-sector comparison: compact table of all sector insights.
4. Macro evidence: upcoming or recent macro events connected to the sector reasoning when available.

The design should stay operational and dashboard-like. It should not use a landing-page hero, decorative backgrounds, oversized cards, or explanatory help text. The UI should be dense enough for repeated use, but with a clear first-read hierarchy.

## Data Inputs

The initial implementation should consume existing frontend data:

- `day.market_regime`
  - `regime`
  - `confidence`
  - `drivers`
  - `implication`
  - optional `sub_regime`
  - optional `forward_signals`
- `day.tickers`
  - `symbol`
  - `data_snapshot.Sector`
  - `data_snapshot.Daily Change`
  - `price_action.rs_vs_sector_etf` when available
  - `decision.action`
  - `decision.conviction`
  - `decision.factors.macro_regime`
  - `decision.factors.regime_adjustment`
  - `decision.factors.macro_event`
  - `decision.factor_reasoning.macro_regime`
- `day.macro_context`
  - `macro_narrative`
  - `macro_events[].affected_sectors`
  - `upcoming_macro_events[].sensitivity_tags`
  - `upcoming_macro_events[].market_bias`
  - `portfolio_event_sensitivity[]` if useful for evidence text

No output JSON fields are required for the first version. If a later iteration moves this calculation into the output layer, that should be a separate additive schema change documented in `docs/output.md`.

## Derived Model

Create a pure frontend derivation function, tentatively named `deriveSectorMoodInsights()`. It should accept the current day data and return a stable list of sector insights.

Each insight should include:

- sector key
- display label
- ticker count
- average daily change
- positive ticker ratio when computable
- top gainer
- top loser
- representative tickers
- regime fit label
- score
- classification: `focus`, `neutral`, or `watch`
- short rationale
- optional macro evidence snippets

The function should be deterministic and independent of React rendering so it can be unit tested with small fixtures.

## Scoring Direction

The sector score should combine four signals:

- Price flow, approximately 35%: average daily change, positive ticker ratio, top gainer/top loser.
- Regime fit, approximately 35%: sector-level aggregation of macro and regime-related decision factors.
- Ticker signal, approximately 20%: conviction, decision action, and representative strength inside the sector.
- Event exposure, approximately 10%: macro events or sensitivity tags that support caution or attention.

The exact implementation may normalize these inputs pragmatically based on the available data, but the relative priority should stay intact: market mood alignment and current sector flow matter most, ticker strength is supporting evidence, and event exposure is a tie-breaker or rationale enhancer.

## Classification Rules

Classify sector insights as follows:

- `focus`: top-scoring sectors whose price flow and regime fit do not materially conflict.
- `watch`: low-scoring sectors, sectors with negative regime fit, or sectors where macro/event exposure creates a caution signal.
- `neutral`: remaining sectors or sectors with mixed evidence.

The top briefing should show two to three focus sectors and two to three watch sectors. If fewer qualifying sectors exist, show only the available sectors. Do not force a focus or watch label when evidence is weak.

"주의 섹터" must not read like a sell instruction. Wording should frame watch sectors as lower priority, relative-strength checks, event-risk checks, or volatility checks.

## Component Design

Add or refactor around these frontend units:

- `MarketMoodSectorBriefing`
  - Renders the connected top briefing.
  - Receives `marketRegime`, `macroContext`, and `tickers`, or receives prederived insights from the parent.
  - Displays regime summary and focus/watch lanes.
- `deriveSectorMoodInsights`
  - Pure calculation helper.
  - Groups tickers by sector and produces the derived sector model.
- `SectorMoodLane`
  - Renders either the focus lane or the watch lane.
  - Handles empty lane states without changing layout dramatically.
- `SectorMoodComparison`
  - Renders the compact full-sector comparison table.
  - Can replace or evolve the current `SectorSummary` role.

`Dashboard.tsx` should keep the same high-level accordion structure and insert the new briefing in the "오늘 시장 분위기" section. Existing macro and market overview components should remain available unless the implementation reveals direct duplication that should be removed in a targeted way.

## Visual And Content Rules

Use restrained dashboard styling consistent with the current app:

- No marketing-style hero section.
- No nested card stacks.
- Cards should be used only for functional panels.
- Desktop should use two-column briefing lanes.
- Mobile should stack lanes and keep ticker chips readable.
- Text must not overflow cards, chips, or table cells.
- Use clear Korean labels for sector names and statuses.

Fix any currently visible Korean label mojibake in the touched sector UI. This cleanup is in scope because broken labels directly affect the readability goal.

Suggested labels:

- `주목 섹터`
- `주의 섹터`
- `중립`
- `정합 높음`
- `정합 낮음`
- `확인 필요`
- `섹터 데이터 부족`

## Empty And Partial Data States

If `market_regime` is missing, the briefing should still show sector comparison when sector data exists, with neutral market wording.

If sector data is missing or too sparse, the section should show a compact empty state such as "섹터 데이터 부족" and keep the existing market regime or macro panels visible.

If daily change values are missing, the calculation should avoid displaying misleading percentages and should reduce confidence in price-flow scoring.

If macro evidence is unavailable, the UI should omit the evidence snippets rather than showing placeholder text.

If all sectors classify as neutral, the top lanes should avoid forced conclusions. The comparison table can still show the ranked neutral sectors.

## Testing Plan

Add focused tests at the level of risk:

- Unit tests for `deriveSectorMoodInsights`
  - groups tickers by sector
  - computes average daily change
  - chooses representative tickers
  - classifies focus/watch/neutral sectors
  - handles missing sector, missing daily change, and empty ticker arrays
- Component tests for `MarketMoodSectorBriefing`
  - renders focus and watch lanes with representative ticker chips
  - renders partial data states
  - avoids treating watch sectors as sell recommendations
- Dashboard regression test
  - verifies the "오늘 시장 분위기" section renders with the new briefing and existing market/macro content.

Existing test commands should be used during implementation, likely `npm run test -- <focused test file>` and then the relevant broader test command. Build or lint should be run if the touched frontend package already supports it.

## Documentation Impact

The initial implementation should not change output payload contracts. Therefore no output contract update is required unless the implementation changes exported JSON. If the implementation only changes frontend derivation and presentation, this design spec is the primary documentation artifact.

If a later iteration moves sector mood insights into `output/data/index.json`, update `docs/output.md` and keep the addition backward-compatible.

## Out Of Scope

- New LLM calls.
- New data collection sources.
- Trading automation or real-time signals.
- Backend schema migration for the first version.
- Reinterpreting official `buy`, `watch`, or `avoid` decisions.
- Replacing the whole dashboard layout.

## Completion Criteria

The implementation that follows this design is done when:

- The market mood section shows a connected regime-to-sector-to-ticker briefing.
- Focus and watch sectors are derived from existing data.
- Empty and partial data states render cleanly.
- Korean sector/status labels are readable.
- Focused tests cover derivation and rendering behavior.
- Existing dashboard behavior remains intact.
