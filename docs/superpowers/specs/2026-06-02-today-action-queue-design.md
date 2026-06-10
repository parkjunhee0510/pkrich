# Today Action Queue Design

## Summary

Add a read-only `today_action_queue` section to the strategy simulator output and Backtest page. The feature turns existing simulator candidate data into an operator-friendly queue: which BUY candidates are ready to check for entry, which should wait, which should be skipped, and which existing positions need attention.

The approved direction is A + C:

- A: strengthen entry judgment by making the best current entry candidates easier to compare.
- C: translate backtest state into a practical daily operating report.

This feature must remain observational. It does not create new official recommendations, change BUY/WATCH/AVOID decisions, alter simulator entry ordering, mutate portfolio state, call external data providers, call the LLM, or trigger trading actions.

## Current Context

`strategy_simulator.json` already includes:

- root metadata with `mode: "observational_long_only"` and `basis: "final_action"`;
- Korean presets `conservative`, `balanced`, and `aggressive`;
- each preset's summary, equity curve, trades, open positions, skipped entries, LLM direction diagnostics, and latest BUY `entry_candidates[]`;
- candidate `news_evidence` diagnostics;
- root `news_shadow` for the canonical `strong_news_llm_bull` strategy.

Existing candidate statuses are:

- `entry_ready`: enough data, cash, and position capacity to inspect next open entry.
- `pending_next_open`: no next trading-day open row exists yet.
- `already_held`: the ticker is already in the simulated portfolio.
- `insufficient_cash`: target notional plus trading cost exceeds available cash.
- `max_positions_reached`: the preset's position cap is already full.
- `missing_entry_price`: a next row exists but open price is missing.
- `simulated_entry_closed`: the candidate's next-open entry date is already in the simulation history.

The first implementation uses the `balanced` preset as the default queue source because it is the current middle-ground operating profile and avoids making users compare three conflicting daily action lists. Other presets remain available in the existing preset comparison UI.

## Output Contract

Add a root field to `strategy_simulator.json`:

```json
"today_action_queue": {
  "status": "ok",
  "as_of": "2026-05-29",
  "basis": "final_action",
  "preset_key": "balanced",
  "preset_label": "균형형",
  "summary": {
    "enter_count": 0,
    "watch_count": 9,
    "skip_count": 0,
    "hold_count": 0,
    "top_action": "watch"
  },
  "items": [],
  "position_alerts": [],
  "notes": []
}
```

### Queue Items

Each `items[]` row is derived from one `balanced.entry_candidates[]` row.

```json
{
  "queue": "watch",
  "decision_label": "보류",
  "rank": 1,
  "ticker": "NXT",
  "action_score": 76.0,
  "status": "pending_next_open",
  "status_label": "다음 open 대기",
  "primary_reason": "다음 거래일 open 가격이 생성되면 진입 조건을 다시 확인합니다.",
  "reason_chips": ["다음 open 대기", "뉴스 강함", "LLM 일치", "확신도 67"],
  "blocking_reasons": ["pending_next_open"],
  "positive_reasons": ["strong_news", "llm_aligned"],
  "candidate_ref": {
    "preset": "balanced",
    "candidate_rank": 1
  },
  "candidate": { "...": "original candidate payload" }
}
```

`candidate` includes the original candidate row as a nested object to keep the UI from rejoining data across sections. This is presentation duplication only; the canonical candidate remains `presets.balanced.entry_candidates[]`.

### Queue Values

`queue` is one of:

- `enter`: candidate status is `entry_ready`.
- `watch`: candidate status is `pending_next_open`, `missing_entry_price`, or `already_held`.
- `skip`: candidate status is `insufficient_cash`, `max_positions_reached`, or `simulated_entry_closed`.
- `hold`: reserved for existing open-position alerts; not used for entry candidates.

`decision_label` maps to Korean labels:

- `enter`: `진입 검토`
- `watch`: `보류`
- `skip`: `제외`
- `hold`: `보유 관리`

### Action Score

`action_score` is display-only. It must not change candidate ranking, simulation entries, trades, or official decisions.

The first scoring model is deterministic and bounded to `0..100`:

- Base conviction: up to 40 points from candidate `conviction`.
- Entry readiness: up to 25 points from candidate `status`.
- News evidence: up to 20 points from `news_evidence.strength`, `score`, and `tone`.
- LLM alignment: up to 10 points from `llm_alignment`.
- Risk/reward clarity: up to 5 points when entry, stop, and take-profit prices are all present.

Status contribution:

- `entry_ready`: 25
- `pending_next_open`: 16
- `missing_entry_price`: 10
- `already_held`: 8
- `insufficient_cash`: 4
- `max_positions_reached`: 3
- `simulated_entry_closed`: 0

News contribution:

- `strength == strong`: 12
- `strength == moderate`: 8
- `strength == weak`: 3
- `strength == insufficient`: 0
- Add up to 5 from normalized `news_evidence.score / 100`.
- Add 3 when `tone == bullish`.

LLM contribution:

- `aligned`: 10
- `neutral`: 5
- `missing`: 3
- `conflict`: 0

Risk/reward clarity contribution:

- Add 5 when `entry_price`, `stop_price`, and `take_profit_price` are all numeric.
- Add 0 otherwise.

The final score is rounded to two decimal places.

The exact formula is:

```text
action_score =
  min(max(conviction, 0), 100) * 0.40
  + status_points
  + news_strength_points
  + min(max(news_evidence.score, 0), 100) * 0.05
  + news_tone_points
  + llm_points
  + risk_reward_points
```

Missing numeric values contribute `0` for their component. The final result is clamped to `0..100`.

### Reasons

`blocking_reasons[]` uses stable machine-readable reason codes:

- `pending_next_open`
- `missing_entry_price`
- `already_held`
- `insufficient_cash`
- `max_positions_reached`
- `simulated_entry_closed`
- `weak_news_evidence`
- `llm_conflict`
- `risk_reward_missing`

`positive_reasons[]` uses stable machine-readable reason codes:

- `entry_ready`
- `strong_news`
- `moderate_news`
- `bullish_news`
- `llm_aligned`
- `cash_available`
- `risk_reward_defined`

`reason_chips[]` is a short Korean display list derived from these codes and the original candidate status. It should be capped to five chips per item to keep the UI compact.

## Position Alerts

`position_alerts[]` is derived from `balanced.open_positions[]`.

```json
{
  "queue": "hold",
  "decision_label": "보유 관리",
  "ticker": "AAPL",
  "priority": 1,
  "alert_score": 64.0,
  "primary_reason": "보유 중인 포지션의 미실현 손익과 보유 기간을 확인합니다.",
  "reason_chips": ["보유 중", "수익률 +4.2%", "보유 12일"],
  "position_ref": {
    "preset": "balanced",
    "ticker": "AAPL"
  },
  "position": { "...": "original open position payload" }
}
```

The first implementation keeps position alerts simple:

- include all open positions from the `balanced` preset;
- sort by absolute `return_pct` descending, then `holding_days` descending, then ticker;
- derive chips from return percentage, holding days, and LLM alignment;
- do not infer stop-loss or take-profit proximity unless the open-position payload already carries enough data.

`position` includes the original open-position row as a nested object. This keeps the UI display-only and avoids recomputing or rejoining portfolio state on the frontend.

## UI Design

Add a new Backtest page section before the existing entry-candidate section.

Section order:

1. `오늘 행동 큐`
2. `오늘 진입 후보`
3. `뉴스 Shadow 성과`
4. `과거 전략 성과`
5. `거래 상세`

The new section contains:

- three summary tiles: `진입 검토`, `보류`, `제외`;
- optional `보유 관리` tile when `position_alerts[]` is non-empty;
- top queue item cards, sorted by queue priority and action score;
- compact chips explaining why a row is enter/watch/skip;
- an empty state when there are no queue items or position alerts.

Queue display priority is:

1. `enter`
2. `watch`
3. `hold`
4. `skip`

Within the same queue bucket, items sort by score descending, then candidate rank ascending when present, then ticker ascending. `top_action` is the highest-priority queue bucket with at least one item or alert; if every bucket is empty, it is `none`.

Queue card display:

- ticker and decision label;
- action score or alert score;
- primary reason;
- up to five reason chips;
- entry date/price when present;
- news evidence compact label when present;
- LLM alignment.

Frontend must display finalized JSON as-is. It must not recompute queue classification or action scores.

## Health Validation

`src/output/health_strategy_simulator.py` should validate:

- root `today_action_queue` exists;
- `status` is `ok` or `insufficient_data`;
- `as_of`, `basis`, `preset_key`, and `preset_label` are strings;
- `summary` contains non-negative integer counts for `enter_count`, `watch_count`, `skip_count`, and `hold_count`;
- `top_action` is one of `enter`, `watch`, `skip`, `hold`, or `none`;
- `items` and `position_alerts` are lists;
- each queue item has the required string, number, list, and object fields;
- `queue` values are restricted to the documented enum;
- `action_score` and `alert_score` are numbers from `0..100`;
- `reason_chips`, `blocking_reasons`, and `positive_reasons` are string lists;
- nested `candidate` and `position` objects may be validated only to the minimum shape needed for safe UI rendering.

The validator should reject malformed queue payloads but should not perform financial recomputation.

## Implementation Boundaries

Allowed:

- deterministic helper functions inside `src/utils/strategy_simulator.py`;
- additive root field in `strategy_simulator.json`;
- health-check validation for the new root field;
- TypeScript contracts and Backtest page rendering;
- generated artifact refresh from existing CSVs;
- docs update.

Not allowed:

- external API calls;
- LLM calls;
- decision recomputation;
- model routing changes;
- factor-weight changes;
- live trading actions;
- portfolio mutation;
- changing simulator entry/trade behavior;
- changing existing preset candidate ordering.

## Testing Plan

Backend unit coverage:

- `today_action_queue` exists on ok payloads and uses `balanced` as `preset_key`.
- `entry_ready` candidates become `enter`.
- `pending_next_open` and `missing_entry_price` candidates become `watch`.
- `insufficient_cash`, `max_positions_reached`, and `simulated_entry_closed` candidates become `skip`.
- `action_score` is bounded to `0..100`.
- strong news, LLM aligned candidates score above otherwise-similar weak/conflict candidates.
- existing `entry_candidates[]` order is unchanged by queue scoring.
- insufficient-data payloads include an empty queue with `status: "insufficient_data"`.

Health-check coverage:

- valid queue payload accepted;
- missing root `today_action_queue` rejected;
- invalid queue enum rejected;
- invalid score range rejected;
- missing summary count rejected;
- malformed reason lists rejected;
- malformed nested candidate or position object rejected only where required for UI safety.

Frontend coverage:

- summary tiles render enter/watch/skip counts;
- top queue card renders ticker, decision label, score, reason, and chips;
- empty queue state renders safely;
- queue section appears before `오늘 진입 후보`;
- missing optional nested candidate fields do not crash the UI.

Generated artifact checks:

- `output/data/strategy_simulator.json` contains `today_action_queue`;
- `web/public/output/data/strategy_simulator.json` matches byte-for-byte;
- `python -m src.cli.output_health_check` passes without strategy-simulator hard issues.

## Completion Criteria

The feature is complete when:

- `today_action_queue` is generated from local simulator inputs only;
- the Backtest page shows the approved daily operating section;
- health checks validate the new shape;
- generated output and web mirror match;
- documentation describes the read-only contract;
- tests and build pass;
- existing official decisions, simulator trades, entry order, and portfolio behavior are unchanged.
