# AI Recommendation Backtest Design

## Status

Approved for spec review on 2026-06-01.

## Context

The project already tracks historical signal outcomes through
`output/data/signal_tracker.csv`, exports read-only analytics through
`output/data/analysis_performance.json`, and renders those analytics on the
`/backtest` page.

The requested feature is an AI backtesting function. For v1, "AI
recommendation" means the finalized decision action recorded in signal history:
`buy`, `watch`, or `avoid`. This intentionally uses the final decision output,
not the separate `llm_direction` text-derived direction. The LLM-vs-final-action
comparison remains a future extension.

The feature must remain observational. It must not change official decisions,
model routing, factor weights, portfolio state, collection behavior, or any
trading automation.

## Goals

- Show whether finalized AI recommendations were followed by favorable realized
  returns.
- Make `buy`, `watch`, and `avoid` performance easy to inspect on `/backtest`.
- Highlight high-conviction recommendation performance.
- Surface best and worst recommendation examples so summary metrics can be
  traced back to concrete rows.
- Reuse existing artifacts and pipeline flow without new external data fetching
  or LLM calls.

## Non-Goals

- No new trading strategy simulator in v1.
- No entry, exit, stop-loss, take-profit, slippage, or position-sizing model.
- No direct use of `llm_direction` as the primary recommendation basis in v1.
- No frontend-side recomputation of performance metrics.
- No automatic update to official decision thresholds, factor weights, or
  recommendations based on the backtest results.

## Accepted Approach

Extend `output/data/analysis_performance.json` with an additive
`ai_recommendation_backtest` field.

This is preferred over a new `ai_backtest_summary.json` because
`analysis_performance.json` is already the read-only shadow analytics artifact
consumed by the Backtest page. Keeping the v1 data in this file avoids a wider
output contract, mirror policy, and frontend loading surface.

The frontend must consume the finalized JSON payload as-is. All calculations
belong in backend/output analytics helpers.

## Data Contract

`analysis_performance.json` gains this additive root field:

```json
{
  "ai_recommendation_backtest": {
    "status": "ok",
    "basis": "final_action",
    "horizons": ["1d", "5d", "20d"],
    "summary": {
      "sample_count": 129,
      "completed_20d_count": 129,
      "best_action": "buy",
      "worst_action": "avoid",
      "notes": []
    },
    "by_action": {
      "buy": {
        "1d": {},
        "5d": {},
        "20d": {}
      },
      "watch": {
        "1d": {},
        "5d": {},
        "20d": {}
      },
      "avoid": {
        "1d": {},
        "5d": {},
        "20d": {}
      }
    },
    "conviction_buckets": {},
    "ticker_leaderboard": [],
    "notable_examples": {
      "best": [],
      "worst": []
    }
  }
}
```

The field is additive and backward-compatible. Existing consumers may ignore it.
New frontend consumers should hide the AI backtesting section when the field is
absent.

### Window Stats

Each action and horizon stat should include:

- `sample_count`: total rows for the action.
- `completed_count`: rows with the relevant `evaluated_<horizon>d` flag set.
- `avg_return`: numeric average return, or `null`.
- `median_return`: numeric median return, or `null`.
- `win_rate`: numeric rate for `buy` and `avoid`, or `null` for `watch`.
- `loss_rate`: numeric rate for `buy` and `avoid`, or `null` for `watch`.
- `best_return`: numeric best return, or `null`.
- `worst_return`: numeric worst return, or `null`.
- `missing_count`: rows not yet evaluated for the horizon.

### Conviction Buckets

High-conviction analysis uses the existing `conviction` column:

- `65_80`: confident recommendations.
- `80_100`: very strong recommendations.

The first implementation should emphasize `buy` outcomes in these buckets while
preserving room to report `avoid` and `watch` counts.

### Ticker Leaderboard

Ticker rows should include:

- `ticker`
- `signals`
- `buy_signals`
- `avoid_signals`
- `completed_5d_count`
- `completed_20d_count`
- `avg_return_5d`
- `avg_return_20d`
- `win_rate_5d`
- `win_rate_20d`

Sorting should avoid overpromoting tiny samples. Prefer completed 20-day sample
count first, then 20-day average return, then 5-day average return.

### Notable Examples

`notable_examples.best` and `notable_examples.worst` should each contain up to
five rows with:

- `signal_date`
- `ticker`
- `action`
- `conviction`
- `return_5d`
- `return_20d`
- `catalyst_tag`
- `regime`

Best and worst examples are ranked by completed 20-day recommendation outcome
when available. If 20-day data is missing, 5-day data may be used as a fallback
for examples only.
b 
## Computation Semantics

Each `signal_tracker.csv` row is evaluated independently.

For `buy`, a recommendation succeeds when realized return is positive:

- `return_1d > 0`
- `return_5d > 0`
- `return_20d > 0`

For `avoid`, a recommendation succeeds when realized return is non-positive:

- `return_1d <= 0`
- `return_5d <= 0`
- `return_20d <= 0`

For `watch`, no directional win rate is reported. The payload still reports
sample count, completed count, average return, median return, return extremes,
and missing count.

Numeric parsing should follow the existing output analytics pattern:

- parse strings such as `+4.77%` into numeric `4.77`
- treat `N/A`, empty strings, invalid strings, and unevaluated rows as missing
- do not throw because one row has malformed optional data

## Architecture

### Backend Analytics

Add a function such as `build_ai_recommendation_backtest(rows)` beside the
existing helpers in `src/utils/performance_analytics.py`.

The helper should be pure and deterministic:

- input: loaded signal tracker rows
- output: a JSON-serializable dictionary-
- no file IO
- no network IO
- no LLM calls
- no dependency on frontend code

### Output Writer

`src/output/analysis_performance.py` should include the new helper result in
`build_analysis_performance_payload()`.

The writer should continue to write `analysis_performance.json` with the shared
schema version and mirror it to `web/public/output/data/analysis_performance.json`
through the existing sync path.

### Frontend Types

`web/src/types/index.ts` should add TypeScript types for
`ai_recommendation_backtest`. The field should be optional on
`AnalysisPerformancePayload` to tolerate older committed payloads or stale local
web mirrors.

### Backtest UI

The `/backtest` page should render an AI Recommendation Backtest section after
the current analysis performance panel.

The section title should be:

```text
AI 추천 백테스팅
```

The short explanatory copy should be:

```text
최종 buy / watch / avoid 판단이 이후 1일, 5일, 20일 수익률과 얼마나 맞았는지 추적합니다.
```

The section should show:

- summary cards for 20-day buy win rate, high-conviction buy performance, avoid
  defense success rate, and evaluated sample count
- an action-by-horizon table for `buy`, `watch`, and `avoid`
- best recommendation examples
- worst recommendation examples
- a small observational footnote stating that these metrics do not change
  official decisions or execution logic

The frontend must not recompute metrics from raw signal rows.

## Empty And Error States

If there are no signal rows, emit a stable insufficient-data payload:

```json
{
  "status": "insufficient_data",
  "basis": "final_action",
  "horizons": ["1d", "5d", "20d"],
  "summary": {
    "sample_count": 0,
    "completed_20d_count": 0,
    "best_action": null,
    "worst_action": null,
    "notes": ["No tracked signals are available yet."]
  },
  "by_action": {},
  "conviction_buckets": {},
  "ticker_leaderboard": [],
  "notable_examples": {
    "best": [],
    "worst": []
  }
}
```

If rows exist but none are evaluated for a horizon, keep the action stats
present with `completed_count: 0`, numeric metric fields as `null`, and
`missing_count` equal to the number of action rows.

If some optional columns are missing from older rows, compute with available
fields and skip only the missing metric. For example, a row without `conviction`
can still contribute to action performance but not conviction buckets.

## Output Health Check

The output health check should validate the minimum shape of
`ai_recommendation_backtest` when present in `analysis_performance.json`.

Validation should check:

- root field is an object
- `status` is a non-empty string
- `basis` equals `final_action`
- `horizons` is a string list
- `summary` is an object with non-negative counts
- `by_action` is an object
- nested horizon metric fields are numbers, null, or non-negative integers as
  appropriate
- `conviction_buckets` is an object
- `ticker_leaderboard` is a list
- `notable_examples.best` and `notable_examples.worst` are lists

Freshly generated payloads should include the field. Older payloads should not
crash frontend rendering, but output tests for generated analytics should expect
the field.

## Tests

### Backend Unit Tests

Extend `tests/test_performance_analytics.py`.

Required cases:

- `buy` treats positive returns as wins.
- `avoid` treats zero or negative returns as wins.
- `watch` reports no win rate.
- missing or invalid return values are counted as missing.
- `65_80` and `80_100` conviction buckets are assigned correctly.
- ticker leaderboard counts action types and completed windows correctly.
- best and worst examples rank by recommendation outcome.
- empty input emits `insufficient_data`.

### Output Tests

Extend `tests/test_analysis_performance_output.py` and output schema fixtures as
needed.

Required cases:

- `write_analysis_performance_output()` includes
  `ai_recommendation_backtest`.
- generated JSON remains parseable and schema-versioned.
- the health check accepts a valid AI backtest shape.
- the health check rejects malformed nested AI backtest metrics.

### Frontend Tests

Extend the existing Backtest analysis performance test coverage.

Required cases:

- `/backtest` renders `AI 추천 백테스팅` when the payload includes the field.
- buy win rate, high-conviction buy, avoid success rate, and evaluated samples
  are visible.
- best and worst examples render.
- the Backtest page does not crash when the field is absent.
- insufficient-data state renders a compact message.

## Verification Commands

The implementation should be verified with:

```powershell
python -m pytest tests/test_performance_analytics.py tests/test_analysis_performance_output.py tests/test_output_health_check.py
npm --prefix web test -- BacktestAnalysisPerformance
python -m src.cli.output_health_check
```

If generated output files are changed during implementation, run the health
check after regenerating and syncing web public mirrors.

## Documentation Updates For Implementation

When this design is implemented, update:

- `docs/output.md` to document `ai_recommendation_backtest` under Analysis
  Performance Outputs.
- Any frontend/UI documentation that describes `/backtest`, if the UI layout
  description is maintained as current behavior.

## Future Extensions

- Add an `llm_direction` comparison panel to show when the LLM text direction
  agrees or conflicts with final action.
- Add a separate strategy simulator with entry, exit, stop-loss, take-profit,
  fees, and slippage.
- Add rolling windows so recommendation quality can be compared by month or
  market regime.
- Add benchmark-relative returns after an explicit benchmark contract is
  approved.
