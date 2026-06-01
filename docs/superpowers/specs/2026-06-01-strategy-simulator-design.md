# Long-Only Strategy Simulator Design

## Status

Approved for spec review on 2026-06-01.

## Context

The project already exports read-only historical signal outcomes through
`backtest_summary.json`, shadow analysis telemetry through
`analysis_performance.json`, and finalized AI recommendation backtest telemetry
through `analysis_performance.ai_recommendation_backtest`.

The next requested feature is a strategy simulator. Unlike the existing 20-day
return summaries, this feature models a simple historical portfolio following
finalized `buy` / `watch` / `avoid` actions. The selected direction is:

- Build the strategy simulator as the primary feature.
- Keep LLM-vs-rule direction comparison as a diagnostic lens on simulator
  results, not as a trading rule.
- Keep the simulator observational. It must not change official decisions,
  model routing, factor weights, portfolio state, collection behavior, or any
  live trading behavior.

## Goals

- Answer: "What would have happened if the finalized recommendations were
  followed as a long-only strategy?"
- Compare three Korean-named presets: `보수형`, `균형형`, and `공격형`.
- Model entry, exit, stop-loss, take-profit, transaction fees, slippage, cash
  limits, and open positions.
- Show realized and unrealized performance separately.
- Surface LLM direction alignment diagnostics for trades so simulator results
  can be interpreted by `signal_direction` vs `llm_direction` agreement.
- Reuse existing `signal_tracker.csv` and `price_history.csv` data without new
  external calls or LLM calls.

## Non-Goals

- No live broker integration.
- No trading automation.
- No short selling in v1.
- No leverage in v1.
- No frontend-side recomputation of strategy metrics.
- No user-editable custom strategy parameters in v1.
- No automatic update to official recommendations, thresholds, factor weights,
  or model routing based on simulator results.
- No new data provider or real-time price collection.

## Accepted Approach

Add a new independent output artifact:

```text
output/data/strategy_simulator.json
web/public/output/data/strategy_simulator.json
```

This is preferred over adding another field to `analysis_performance.json` or
`backtest_summary.json` because the simulator has a larger and different shape:
presets, portfolio equity curves, trades, open positions, skipped entries, and
diagnostic breakdowns. Keeping it separate preserves the existing analysis and
backtest artifact responsibilities.

The `/backtest` page should load this artifact and render it below the AI
recommendation backtest section. The frontend must display the finalized JSON
as-is and must not recompute trades, equity, stop-losses, take-profits, or
diagnostics.

## Strategy Rules

### Strategy Mode

The simulator is long-only.

- `buy`: eligible for a long entry.
- `watch`: no new entry; existing long positions remain open.
- `avoid`: no short entry. If a position is already open for the ticker, it
  schedules a long exit.

### Entry Timing

A `buy` signal becomes eligible for entry on the next available trading day for
that ticker.

- Entry price: next trading day `open`.
- If the next trading day or open price is missing, the entry is skipped with
  reason `missing_entry_price`.
- If the ticker is already held, the new `buy` is skipped with reason
  `already_held`.
- If the preset's position target cannot be funded from available cash after
  entry cost, the entry is skipped with reason `insufficient_cash`.
- If the preset's max position count is already reached, the entry is skipped
  with reason `max_positions_reached`.

This rule avoids using same-day or future information unavailable when the
recommendation was produced.

### Buy Priority

When multiple `buy` entries are eligible on the same trading day and the
simulator cannot take all of them because of cash or position limits, entries
are processed in this deterministic order:

1. Higher numeric `conviction`.
2. Earlier `signal_date`.
3. Ticker ascending.

Rows with missing or invalid conviction remain eligible but sort after rows
with numeric conviction.

### Exit Timing

Open positions can exit by stop-loss, take-profit, or later `avoid`.

The daily processing order for each ticker is:

1. Execute scheduled `avoid` exits at that trading day's `open`.
2. Execute scheduled entries at that trading day's `open`.
3. Check intraday stop-loss and take-profit using that trading day's `low` and
   `high`.

An `avoid` signal schedules an exit on the next available trading day `open`.
This mirrors entry timing and avoids using same-day signal information as if it
were known before the trading session.

### Stop-Loss And Take-Profit

After entry, each open position has preset-specific stop-loss and take-profit
thresholds based on the entry price.

- Stop-loss is triggered when daily `low <= stop_price`.
- Take-profit is triggered when daily `high >= take_profit_price`.
- If both thresholds are touched on the same day, the simulator uses the
  pessimistic assumption and records the stop-loss first.
- Stop-loss exits use the stop threshold price.
- Take-profit exits use the take-profit threshold price.

### Open Positions

Because selected exit rule is "hold until stop, take-profit, or later `avoid`",
positions may remain open at the end of the available price history.

Open positions are marked to market using the latest available `close` for the
ticker. Total portfolio performance includes unrealized P&L, while realized P&L
and unrealized P&L are reported separately.

### Cash And Sizing

The simulator starts each preset with an initial capital of `100000`.

- Cash earns no interest.
- Fractional shares are allowed for deterministic sizing.
- Total invested capital cannot exceed available cash.
- No leverage is allowed.
- A target entry notional is `current_portfolio_value * position_size_pct`.
- If available cash cannot fund target notional plus entry costs, the entry is
  skipped rather than partially filled.

## Presets

Internal keys stay ASCII for stable JSON contracts. UI labels are Korean.

| Key | Label | Description | Position Size | Max Positions | Stop-Loss | Take-Profit |
|-----|-------|-------------|---------------|---------------|-----------|-------------|
| `conservative` | `보수형` | 작게 사고 빠르게 방어 | 5% | 6 | -6% | +12% |
| `balanced` | `균형형` | 기본 비교 기준 | 10% | 8 | -8% | +18% |
| `aggressive` | `공격형` | 크게 사고 길게 노림 | 15% | 10 | -10% | +25% |

All presets share the same cost assumptions:

- Buy-side fee: 0.10%.
- Buy-side slippage: 0.05%.
- Sell-side fee: 0.10%.
- Sell-side slippage: 0.05%.
- Round-trip cost: 0.30%.

For entry, cash outflow is:

```text
notional * (1 + fee_rate + slippage_rate)
```

For exit, cash inflow is:

```text
shares * exit_price * (1 - fee_rate - slippage_rate)
```

## LLM Direction Diagnostics

LLM direction diagnostics are observational and must not influence entries,
exits, sizing, or priority.

For each trade, classify the entry signal row by comparing:

- `signal_direction`: rule/final signal direction.
- `llm_direction`: direction extracted from the LLM text.

Diagnostic buckets:

- `aligned`: both fields are present and equal.
- `conflict`: both fields are present and not equal.
- `missing`: either direction is blank or not one of `bull`, `bear`, `neutral`.

Each preset reports performance by diagnostic bucket:

- `trade_count`
- `closed_trade_count`
- `open_position_count`
- `realized_pnl`
- `unrealized_pnl`
- `avg_trade_return_pct`
- `win_rate`

This gives the user a way to inspect whether trades worked better when the LLM
text direction agreed with the rule/final signal direction.

## Data Contract

`strategy_simulator.json` root shape:

```json
{
  "schema_version": 1,
  "status": "ok",
  "as_of": "2026-06-01",
  "mode": "observational_long_only",
  "basis": "final_action",
  "inputs": {},
  "assumptions": {},
  "presets": {},
  "notes": []
}
```

### Root Fields

- `schema_version`: shared output schema version.
- `status`: `ok` or `insufficient_data`.
- `as_of`: latest source date used by the simulator, preferably latest
  available price date.
- `mode`: `observational_long_only`.
- `basis`: `final_action`.
- `inputs`: source row counts and date ranges.
- `assumptions`: selected strategy assumptions and shared costs.
- `presets`: object keyed by `conservative`, `balanced`, and `aggressive`.
- `notes`: explanatory strings.

If there are no usable signal rows or no usable price rows, emit a stable
`insufficient_data` payload with empty `presets`.

### Preset Shape

Each preset contains:

```json
{
  "label": "균형형",
  "description": "기본 비교 기준",
  "params": {
    "initial_capital": 100000,
    "position_size_pct": 0.1,
    "max_positions": 8,
    "stop_loss_pct": -0.08,
    "take_profit_pct": 0.18,
    "fee_rate": 0.001,
    "slippage_rate": 0.0005
  },
  "summary": {},
  "equity_curve": [],
  "trades": [],
  "open_positions": [],
  "skipped_entries": {},
  "llm_direction_diagnostics": {}
}
```

### Summary Fields

Each `summary` should include:

- `initial_capital`
- `ending_equity`
- `total_return_pct`
- `realized_pnl`
- `unrealized_pnl`
- `cash`
- `cash_pct`
- `invested_value`
- `invested_pct`
- `max_drawdown_pct`
- `trade_count`
- `closed_trade_count`
- `open_position_count`
- `winning_trade_count`
- `losing_trade_count`
- `win_rate`
- `avg_closed_trade_return_pct`
- `skipped_buy_count`

### Equity Curve Points

Each point should include:

- `date`
- `equity`
- `cash`
- `invested_value`
- `realized_pnl`
- `unrealized_pnl`
- `drawdown_pct`
- `open_position_count`

### Trade Rows

Each closed trade row should include:

- `ticker`
- `entry_signal_date`
- `entry_date`
- `entry_price`
- `exit_signal_date`
- `exit_date`
- `exit_price`
- `exit_reason`: `stop_loss`, `take_profit`, or `avoid`
- `shares`
- `notional`
- `entry_cost`
- `exit_cost`
- `realized_pnl`
- `return_pct`
- `holding_days`
- `conviction`
- `signal_direction`
- `llm_direction`
- `llm_alignment`: `aligned`, `conflict`, or `missing`

### Open Position Rows

Each open position row should include:

- `ticker`
- `entry_signal_date`
- `entry_date`
- `entry_price`
- `latest_date`
- `latest_close`
- `shares`
- `notional`
- `market_value`
- `unrealized_pnl`
- `return_pct`
- `holding_days`
- `conviction`
- `signal_direction`
- `llm_direction`
- `llm_alignment`

### Skipped Entries

`skipped_entries` should include:

- `total_count`
- `by_reason`
- `examples`

Example reasons:

- `missing_entry_price`
- `already_held`
- `insufficient_cash`
- `max_positions_reached`

Examples should be bounded to a deterministic small number, such as the first 20
by signal date and ticker.

## Architecture

### Backend Helper

Add a pure deterministic helper, for example:

```text
src/utils/strategy_simulator.py::build_strategy_simulator(signal_rows, price_rows)
```

The helper should:

- Accept already-loaded signal and price rows.
- Perform no file IO.
- Perform no network IO.
- Perform no LLM calls.
- Return a JSON-serializable dictionary.
- Keep calculations deterministic.

### Output Writer

Add an output writer, for example:

```text
src/output/strategy_simulator.py::write_strategy_simulator_output()
```

The writer should:

- Load `output/data/signal_tracker.csv`.
- Load `output/data/price_history.csv`.
- Write `output/data/strategy_simulator.json`.
- Mirror to `web/public/output/data/strategy_simulator.json` through the
  existing web sync path.
- Use the shared safe JSON writer pattern where appropriate.

The default JSON output path should produce this artifact after signal and price
history artifacts exist. The local performance-output regeneration command
should also be able to regenerate this artifact from existing output data
without rerunning collection, analysis, or decision logic.

### Health Check

Extend the output health check to validate `strategy_simulator.json` when
present.

Validation should check:

- Root is an object.
- `status` is `ok` or `insufficient_data`.
- `mode` is `observational_long_only`.
- `basis` is `final_action`.
- `inputs`, `assumptions`, `presets`, and `notes` have expected types.
- For `ok`, all three preset keys are present.
- Preset params contain finite numeric values and non-negative counts where
  appropriate.
- Summary numeric fields are numbers or null where appropriate.
- Equity curve, trades, open positions, and skipped entry examples are lists.
- Trade and open-position rows contain required fields with valid types.
- LLM diagnostic buckets are objects with numeric counts and nullable metrics.

Backward compatibility should allow the file to be absent until implementation
is rolled into generation.

### Web Sync

Add `strategy_simulator.json` to the default web sync contract when generated.
The health check should verify source and web mirror match, consistent with
other current-facing public artifacts.

## Backtest UI

The `/backtest` page should load:

```text
output/data/strategy_simulator.json
```

Render a new Strategy Simulator section below the AI recommendation backtest
section.

Recommended UI:

- Summary cards for selected preset:
  - total return
  - realized P&L
  - unrealized P&L
  - max drawdown
  - win rate
  - open positions
- A preset comparison table for `보수형`, `균형형`, and `공격형`.
- A segmented control or tabs to inspect one preset at a time.
- An equity curve for the selected preset using finalized backend data.
- An open positions table.
- A recent closed trades table.
- A skipped entries summary.
- An LLM direction diagnostics table comparing `aligned`, `conflict`, and
  `missing` buckets.

The UI should make clear that:

- This is a historical simulation.
- It is not investment advice.
- It does not trigger trades.
- AVOID means exit/avoid long exposure, not short selling.

If the artifact is absent, the section should stay hidden. If status is
`insufficient_data`, render a compact empty state.

## Tests

### Backend Unit Tests

Add focused tests for the simulator helper:

- `buy` enters on the next trading day's open.
- Missing next open skips the entry.
- Stop-loss exits when daily low reaches the threshold.
- Take-profit exits when daily high reaches the threshold.
- When stop-loss and take-profit are both touched on one day, stop-loss wins.
- A later `avoid` exits at the next trading day's open.
- Repeated `buy` while already held is skipped.
- Cash limits skip entries that cannot fund target notional plus entry costs.
- Max position limits skip extra entries.
- Conviction priority chooses higher-conviction entries first.
- Open positions are marked to the latest close and reported separately from
  realized P&L.
- Fees and slippage are deducted on both entry and exit.
- LLM alignment buckets are computed from `signal_direction` and
  `llm_direction`.
- Empty or insufficient input emits stable `insufficient_data`.

### Output Tests

Add output tests for:

- `write_strategy_simulator_output()` writes parseable JSON.
- The generated payload includes all three preset keys.
- The web mirror is written when the web directory exists.
- Health check accepts a valid generated payload.
- Health check rejects malformed root, preset params, summary metrics, trade
  rows, open-position rows, and LLM diagnostic buckets.

### Frontend Tests

Add `/backtest` tests for:

- Strategy simulator section renders when the payload exists.
- Korean preset names render.
- Summary cards render selected preset metrics.
- Open positions and closed trades render when present.
- LLM diagnostic rows render.
- Missing artifact does not crash the page.
- `insufficient_data` renders a compact empty state.

## Documentation Updates For Implementation

When implementation lands, update:

- `docs/output.md` to document `strategy_simulator.json`.
- Any `/backtest` UI documentation that describes current page sections.
- The output health check documentation summary if it lists artifact coverage.

## Verification Commands

Implementation should be verified with at least:

```powershell
python -m pytest tests/test_strategy_simulator.py tests/test_strategy_simulator_output.py tests/test_output_health_check.py
npm --prefix web test -- Backtest
npm --prefix web run build
python -m src.cli.output_health_check
python -m compileall main.py src tests
```

If generated artifacts are changed during implementation, regenerate the output
set and run the health check after web mirror sync.

## Future Extensions

- Add user-editable simulator configuration after a config contract is approved.
- Add benchmark-relative simulator returns.
- Add sector diversification constraints.
- Add short-selling as a separate explicitly approved simulator mode.
- Add monthly and regime rolling simulator summaries.
- Add exportable simulator trade reports.
