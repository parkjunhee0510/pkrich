# PM Queue Korean-First Design

## Goal

Make PM review queue text render in Korean-first form for real use.

## Scope

This change applies only to `pm_view` text generated in `src/output/pm_view.py`.

Affected fields:

* `swap_candidates[].summary`
* `swap_candidates[].reasons[]`
* `swap_candidates[].overlap_context`
* `swap_candidates[].review_points[]`
* `event_exposure_items[].event_label`
* `event_exposure_items[].summary`
* `event_exposure_items[].reasons[]`
* `event_exposure_items[].review_points[]`
* `today_priority_queue[].summary`
* `today_priority_queue[].reasons[]`
* `empty_states.*`

## Non-Goals

This change does not:

* alter official `buy` / `watch` / `avoid` decisions
* change analyzer-wide prompt language
* change committee output language rules
* add frontend-only translation logic

## Approach

Use output-layer Korean generation in `src/output/pm_view.py`.

Reasons:

* PM queue copy is already assembled in the output layer
* the affected scope is narrow and deterministic
* JSON artifacts, API payloads, and frontend views all become consistent at once
* analyzer prompts remain untouched, which reduces regression risk

## Language Rules

### Korean-First Output

PM queue generated strings must be written in Korean.

Allowed raw values to remain as-is:

* ticker symbols such as `NVDA`
* dates such as `2026-05-01`
* numeric values such as conviction scores or weights

### Event Labels

Known event labels and types should map to Korean labels first.

Examples:

* `Earnings` -> `실적 발표`
* `Dividend Payment Date` -> `배당 지급일`
* `Ex-Dividend Date` -> `배당락일`
* `Fed Meeting` -> `연준 회의`
* `CPI Release` -> `CPI 발표`
* `Developer Conference` -> `개발자 컨퍼런스`
* `Product Launch` -> `신제품 출시`
* `Shareholder Meeting` -> `주주총회`

If the source event label or type is unknown, prefer a natural Korean fallback label instead of English echoing.

### Tone

PM queue copy should read like portfolio-review guidance, not trading-command copy.

Preferred tone:

* `점검하세요`
* `검토가 필요합니다`
* `확인하세요`

Avoid:

* direct sell commands
* aggressive rotation wording
* English boilerplate such as `Review`, `Same sector`, `N/A`

## Data Contract

Field names remain unchanged for schema stability.

Only human-readable values change.

## Implementation Notes

Implementation should introduce small helper functions in `src/output/pm_view.py` for:

* event label normalization
* Korean overlap-context rendering
* Korean summary and reason templates
* safe fallback labels for unknown events or sectors

The output must stay deterministic.

## Testing

Update `tests/test_pm_view.py` to assert Korean-first strings for PM queue output.

Verification should include:

* swap candidate text is Korean
* event exposure text is Korean
* empty states are Korean
* known event labels are translated to Korean
* unknown labels still produce Korean-safe fallback text

After tests, run a real pipeline execution and inspect generated `pm_view` in:

* `output/data/index.json`
* `output/data/dashboard_history.json`

## Success Criteria

The PM review queue appears in Korean-first form across generated JSON and web consumption paths without changing official decision logic.
