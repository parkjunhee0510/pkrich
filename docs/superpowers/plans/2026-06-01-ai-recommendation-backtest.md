# AI Recommendation Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only AI recommendation backtest section that shows whether finalized `buy`, `watch`, and `avoid` actions were followed by favorable 1d, 5d, and 20d realized returns.

**Architecture:** Compute all metrics in backend output analytics from `signal_tracker.csv`, append the result to `analysis_performance.json`, validate the new shape in output health checks, and render it on `/backtest` without frontend recomputation. The feature is observational only and does not alter decisions, model routing, factor weights, or portfolio state.

**Tech Stack:** Python 3, pytest, React 18, TypeScript, Vitest, static JSON artifacts under `output/data`, Vite static mirror under `web/public/output/data`.

---

## File Structure

- Modify: `src/utils/performance_analytics.py`
  - Add pure helper `build_ai_recommendation_backtest(rows)`.
  - Keep parsing and return-window logic beside existing performance analytics helpers.
- Modify: `tests/test_performance_analytics.py`
  - Cover the new helper with focused unit tests.
- Modify: `src/output/analysis_performance.py`
  - Add `ai_recommendation_backtest` to the generated payload.
- Modify: `tests/test_analysis_performance_output.py`
  - Assert the output writer includes the new field.
- Modify: `tests/test_output_schema.py`
  - Keep the existing shape snapshot test passing after fixture regeneration.
- Modify: `tests/fixtures/output_schemas/analysis_performance.shape.json`
  - Update the normalized output shape snapshot.
- Create: `src/output/health_analysis_performance_ai_backtest.py`
  - Validate the optional AI backtest shape when present.
- Modify: `src/output/health_analysis_performance.py`
  - Call the new AI backtest validator.
- Modify: `tests/test_output_health_check.py`
  - Add valid and invalid AI backtest health cases.
- Modify: `web/src/types/index.ts`
  - Add TypeScript interfaces for the new JSON field.
- Create: `web/src/components/AiRecommendationBacktestPanel.tsx`
  - Render summary cards, action table, and notable examples.
- Modify: `web/src/pages/Backtest.tsx`
  - Render the new panel after `AnalysisPerformancePanel`.
- Modify: `web/src/pages/BacktestAnalysisPerformance.test.tsx`
  - Assert the panel renders and remains absent-safe.
- Modify: `docs/output.md`
  - Document the new additive `analysis_performance.json` field.
- Modify generated artifacts after implementation:
  - `output/data/analysis_performance.json`
  - `web/public/output/data/analysis_performance.json`

## Preflight: Git And Existing Spec

**Files:**
- Existing: `docs/superpowers/specs/2026-06-01-ai-recommendation-backtest-design.md`
- Create: `docs/superpowers/plans/2026-06-01-ai-recommendation-backtest.md`

- [ ] **Step 1: Check Git status**

Run:

```powershell
git status --short --branch
```

Expected: shows the approved spec as untracked or modified. The plan file lives under `docs/superpowers/plans/`, which is ignored by the repository-wide `plans/` ignore rule, so add it with `git add -f` in the next step. If Git reports `.git/index.lock` permission errors, close other Git clients and pause OneDrive sync for this repository before proceeding.

- [ ] **Step 2: Commit approved spec and plan**

Run:

```powershell
git add docs/superpowers/specs/2026-06-01-ai-recommendation-backtest-design.md
git add -f docs/superpowers/plans/2026-06-01-ai-recommendation-backtest.md
git commit -m "docs: add ai recommendation backtest plan"
```

Expected: commit succeeds. If the current sandbox still cannot create `.git/index.lock`, continue the implementation but record in the final handoff that commits could not be created from this environment.

---

### Task 1: Backend AI Recommendation Analytics

**Files:**
- Modify: `tests/test_performance_analytics.py`
- Modify: `src/utils/performance_analytics.py`

- [ ] **Step 1: Write failing tests for AI recommendation metrics**

In `tests/test_performance_analytics.py`, add `build_ai_recommendation_backtest` to the import list:

```python
from src.utils.performance_analytics import (
    build_ai_recommendation_backtest,
    build_conviction_calibration,
    build_factor_attribution,
    build_regime_performance,
    build_signal_performance,
)
```

Add this fixture after `ROWS`:

```python
AI_BACKTEST_ROWS = [
    {
        "signal_date": "2026-04-01",
        "ticker": "AAPL",
        "action": "buy",
        "conviction": "72",
        "regime": "risk_on",
        "catalyst_tag": "earnings",
        "return_1d": "+1.00%",
        "return_5d": "+4.00%",
        "return_20d": "+8.00%",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "True",
    },
    {
        "signal_date": "2026-04-02",
        "ticker": "MSFT",
        "action": "avoid",
        "conviction": "82",
        "regime": "risk_off",
        "catalyst_tag": "guidance",
        "return_1d": "+0.00%",
        "return_5d": "-3.00%",
        "return_20d": "-5.00%",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "True",
    },
    {
        "signal_date": "2026-04-03",
        "ticker": "KO",
        "action": "watch",
        "conviction": "51",
        "regime": "neutral",
        "catalyst_tag": "dividend",
        "return_1d": "+0.20%",
        "return_5d": "+0.40%",
        "return_20d": "N/A",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "False",
    },
    {
        "signal_date": "2026-04-04",
        "ticker": "AMD",
        "action": "buy",
        "conviction": "88",
        "regime": "risk_on",
        "catalyst_tag": "product",
        "return_1d": "-1.00%",
        "return_5d": "-2.00%",
        "return_20d": "-6.00%",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "True",
    },
]
```

Add these test methods inside `PerformanceAnalyticsTests`:

```python
    def test_ai_recommendation_backtest_scores_buy_avoid_and_watch(self) -> None:
        payload = build_ai_recommendation_backtest(AI_BACKTEST_ROWS)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["basis"], "final_action")
        self.assertEqual(payload["summary"]["sample_count"], 4)
        self.assertEqual(payload["summary"]["completed_20d_count"], 3)
        self.assertEqual(payload["by_action"]["buy"]["20d"]["sample_count"], 2)
        self.assertEqual(payload["by_action"]["buy"]["20d"]["completed_count"], 2)
        self.assertEqual(payload["by_action"]["buy"]["20d"]["win_rate"], 0.5)
        self.assertEqual(payload["by_action"]["avoid"]["20d"]["win_rate"], 1.0)
        self.assertIsNone(payload["by_action"]["watch"]["20d"]["win_rate"])
        self.assertEqual(payload["by_action"]["watch"]["20d"]["missing_count"], 1)

    def test_ai_recommendation_backtest_builds_conviction_and_examples(self) -> None:
        payload = build_ai_recommendation_backtest(AI_BACKTEST_ROWS)

        self.assertEqual(payload["conviction_buckets"]["65_80"]["sample_count"], 1)
        self.assertEqual(payload["conviction_buckets"]["80_100"]["sample_count"], 2)
        self.assertEqual(payload["conviction_buckets"]["80_100"]["action_counts"], {"avoid": 1, "buy": 1})
        self.assertEqual(payload["notable_examples"]["best"][0]["ticker"], "AAPL")
        self.assertEqual(payload["notable_examples"]["worst"][0]["ticker"], "AMD")
        self.assertEqual(payload["ticker_leaderboard"][0]["ticker"], "AAPL")

    def test_ai_recommendation_backtest_empty_input_is_stable(self) -> None:
        payload = build_ai_recommendation_backtest([])

        self.assertEqual(payload["status"], "insufficient_data")
        self.assertEqual(payload["summary"]["sample_count"], 0)
        self.assertEqual(payload["by_action"], {})
        self.assertEqual(payload["ticker_leaderboard"], [])
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_performance_analytics.py -k ai_recommendation -v
```

Expected: fails because `build_ai_recommendation_backtest` is not defined.

- [ ] **Step 3: Add the backend implementation**

In `src/utils/performance_analytics.py`, add these constants below `BUCKETS`:

```python
AI_ACTIONS = ("buy", "watch", "avoid")
AI_HORIZONS = (1, 5, 20)
AI_CONVICTION_BUCKETS = (
    ("65_80", 65, 80),
    ("80_100", 80, 100),
)
```

Add this function and helpers after `build_factor_attribution()` and before `_window_metrics()`:

```python
def build_ai_recommendation_backtest(rows: list[dict[str, str]]) -> dict[str, Any]:
    tracked_rows = [row for row in rows if _action(row) in AI_ACTIONS]
    if not tracked_rows:
        return _empty_ai_recommendation_backtest()

    by_action = {
        action: {
            f"{horizon}d": _ai_window_metrics(
                [row for row in tracked_rows if _action(row) == action],
                horizon,
                action,
            )
            for horizon in AI_HORIZONS
        }
        for action in AI_ACTIONS
    }
    return {
        "status": "ok",
        "basis": "final_action",
        "horizons": [f"{horizon}d" for horizon in AI_HORIZONS],
        "summary": _ai_summary(tracked_rows, by_action),
        "by_action": by_action,
        "conviction_buckets": _ai_conviction_buckets(tracked_rows),
        "ticker_leaderboard": _ai_ticker_leaderboard(tracked_rows),
        "notable_examples": _ai_notable_examples(tracked_rows),
    }


def _empty_ai_recommendation_backtest() -> dict[str, Any]:
    return {
        "status": "insufficient_data",
        "basis": "final_action",
        "horizons": [f"{horizon}d" for horizon in AI_HORIZONS],
        "summary": {
            "sample_count": 0,
            "completed_20d_count": 0,
            "best_action": None,
            "worst_action": None,
            "notes": ["No tracked signals are available yet."],
        },
        "by_action": {},
        "conviction_buckets": {},
        "ticker_leaderboard": [],
        "notable_examples": {
            "best": [],
            "worst": [],
        },
    }


def _ai_summary(rows: list[dict[str, str]], by_action: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ranked_actions: list[tuple[str, float]] = []
    for action in ("buy", "avoid"):
        stats = by_action.get(action, {}).get("20d", {})
        avg_return = stats.get("avg_return")
        if isinstance(avg_return, (int, float)) and stats.get("completed_count", 0) > 0:
            score = avg_return if action == "buy" else -avg_return
            ranked_actions.append((action, score))
    ranked_actions.sort(key=lambda item: item[1], reverse=True)
    return {
        "sample_count": len(rows),
        "completed_20d_count": sum(1 for row in rows if _return_value(row, 20) is not None),
        "best_action": ranked_actions[0][0] if ranked_actions else None,
        "worst_action": ranked_actions[-1][0] if ranked_actions else None,
        "notes": [
            "AI recommendation backtest is observational and does not change official decisions.",
        ],
    }


def _ai_window_metrics(rows: list[dict[str, str]], horizon: int, action_name: str) -> dict[str, Any]:
    values: list[float] = []
    wins = 0
    losses = 0
    missing_count = 0
    for row in rows:
        value = _return_value(row, horizon)
        if value is None:
            missing_count += 1
            continue
        values.append(value)
        outcome = _recommendation_win(action_name, value)
        if outcome is True:
            wins += 1
        elif outcome is False:
            losses += 1

    completed = len(values)
    win_rate = None
    loss_rate = None
    if action_name in {"buy", "avoid"} and completed:
        win_rate = round(wins / completed, 4)
        loss_rate = round(losses / completed, 4)

    return {
        "sample_count": len(rows),
        "completed_count": completed,
        "avg_return": round(sum(values) / completed, 4) if completed else None,
        "median_return": round(float(median(values)), 4) if completed else None,
        "win_rate": win_rate,
        "loss_rate": loss_rate,
        "best_return": round(max(values), 4) if completed else None,
        "worst_return": round(min(values), 4) if completed else None,
        "missing_count": missing_count,
    }


def _recommendation_win(action_name: str, value: float) -> bool | None:
    if action_name == "buy":
        return value > 0
    if action_name == "avoid":
        return value <= 0
    return None


def _recommendation_score(row: dict[str, str], horizon: int) -> float | None:
    action_name = _action(row)
    value = _return_value(row, horizon)
    if value is None:
        return None
    if action_name == "buy":
        return value
    if action_name == "avoid":
        return -value
    return None


def _ai_conviction_buckets(rows: list[dict[str, str]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, low, high in AI_CONVICTION_BUCKETS:
        bucket_rows = [
            row for row in rows
            if (conviction := _parse_float(row.get("conviction"))) is not None
            and low <= conviction < high
        ]
        action_counts = Counter(_action(row) for row in bucket_rows)
        result[name] = {
            "sample_count": len(bucket_rows),
            "action_counts": dict(sorted(action_counts.items())),
            "by_action": {
                action: {
                    "5d": _ai_window_metrics(
                        [row for row in bucket_rows if _action(row) == action],
                        5,
                        action,
                    ),
                    "20d": _ai_window_metrics(
                        [row for row in bucket_rows if _action(row) == action],
                        20,
                        action,
                    ),
                }
                for action in AI_ACTIONS
            },
        }
    return result


def _ai_ticker_leaderboard(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        ticker = str(row.get("ticker", "") or "").strip().upper()
        if ticker:
            grouped[ticker].append(row)

    leaderboard: list[dict[str, Any]] = []
    for ticker, ticker_rows in grouped.items():
        directional_rows = [row for row in ticker_rows if _action(row) in {"buy", "avoid"}]
        scores_5d = [score for row in directional_rows if (score := _recommendation_score(row, 5)) is not None]
        scores_20d = [score for row in directional_rows if (score := _recommendation_score(row, 20)) is not None]
        leaderboard.append(
            {
                "ticker": ticker,
                "signals": len(ticker_rows),
                "buy_signals": sum(1 for row in ticker_rows if _action(row) == "buy"),
                "avoid_signals": sum(1 for row in ticker_rows if _action(row) == "avoid"),
                "completed_5d_count": len(scores_5d),
                "completed_20d_count": len(scores_20d),
                "avg_return_5d": round(sum(scores_5d) / len(scores_5d), 4) if scores_5d else None,
                "avg_return_20d": round(sum(scores_20d) / len(scores_20d), 4) if scores_20d else None,
                "win_rate_5d": round(sum(1 for score in scores_5d if score > 0) / len(scores_5d), 4) if scores_5d else None,
                "win_rate_20d": round(sum(1 for score in scores_20d if score > 0) / len(scores_20d), 4) if scores_20d else None,
            }
        )
    leaderboard.sort(
        key=lambda item: (
            item["completed_20d_count"],
            item["avg_return_20d"] if item["avg_return_20d"] is not None else float("-inf"),
            item["avg_return_5d"] if item["avg_return_5d"] is not None else float("-inf"),
        ),
        reverse=True,
    )
    return leaderboard


def _ai_notable_examples(rows: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    scored: list[tuple[float, dict[str, str]]] = []
    for row in rows:
        score = _recommendation_score(row, 20)
        if score is None:
            score = _recommendation_score(row, 5)
        if score is not None:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return {
        "best": [_ai_example(row) for _, row in scored[:5]],
        "worst": [_ai_example(row) for _, row in reversed(scored[-5:])],
    }


def _ai_example(row: dict[str, str]) -> dict[str, Any]:
    return {
        "signal_date": str(row.get("signal_date", "") or ""),
        "ticker": str(row.get("ticker", "") or "").strip().upper(),
        "action": _action(row),
        "conviction": _parse_float(row.get("conviction")),
        "return_5d": _return_value(row, 5),
        "return_20d": _return_value(row, 20),
        "catalyst_tag": str(row.get("catalyst_tag", "") or ""),
        "regime": _regime(row),
    }
```

- [ ] **Step 4: Run backend tests**

Run:

```powershell
python -m pytest tests/test_performance_analytics.py -v
```

Expected: all tests in `tests/test_performance_analytics.py` pass.

- [ ] **Step 5: Commit backend analytics**

Run:

```powershell
git add src/utils/performance_analytics.py tests/test_performance_analytics.py
git commit -m "feat: add ai recommendation backtest analytics"
```

Expected: commit succeeds.

---

### Task 2: Wire AI Backtest Into Analysis Performance Output

**Files:**
- Modify: `src/output/analysis_performance.py`
- Modify: `tests/test_analysis_performance_output.py`
- Modify: `tests/test_output_schema.py`
- Modify: `tests/fixtures/output_schemas/analysis_performance.shape.json`

- [ ] **Step 1: Write failing output writer assertion**

In `tests/test_analysis_performance_output.py`, add these assertions after `self.assertIn("action_change_reasons", payload)`:

```python
        self.assertIn("ai_recommendation_backtest", payload)
        self.assertEqual(payload["ai_recommendation_backtest"]["basis"], "final_action")
        self.assertEqual(payload["ai_recommendation_backtest"]["by_action"]["watch"]["5d"]["win_rate"], None)
```

- [ ] **Step 2: Run output test and verify it fails**

Run:

```powershell
python -m pytest tests/test_analysis_performance_output.py -v
```

Expected: fails because `ai_recommendation_backtest` is missing.

- [ ] **Step 3: Add the helper to the output payload**

In `src/output/analysis_performance.py`, add `build_ai_recommendation_backtest` to the import from `src.utils.performance_analytics`:

```python
from src.utils.performance_analytics import (
    build_ai_recommendation_backtest,
    build_conviction_calibration,
    build_factor_attribution,
    build_regime_performance,
    build_signal_performance,
)
```

Then add this field to the dictionary returned by `build_analysis_performance_payload()` immediately after `action_change_reasons`:

```python
        "ai_recommendation_backtest": build_ai_recommendation_backtest(signal_rows),
```

- [ ] **Step 4: Run output writer test**

Run:

```powershell
python -m pytest tests/test_analysis_performance_output.py -v
```

Expected: test passes.

- [ ] **Step 5: Regenerate the analysis performance shape fixture**

Run this mechanical fixture refresh command from the repository root:

```powershell
@'
import json
import tempfile
from datetime import date
from pathlib import Path

from src.output.analysis_performance import write_analysis_performance_output
from src.types import MarketRegime, TickerDecision
from tests.helpers.output_snapshot import normalize_json_shape

with tempfile.TemporaryDirectory() as temp_dir:
    output_root = Path(temp_dir) / "output"
    signal_rows = [
        {
            "signal_date": "2026-04-30",
            "ticker": "AAPL",
            "action": "watch",
            "conviction": "58",
            "regime": "neutral",
            "factors_json": "{\"momentum\": 0.2}",
            "confidence_meta_json": "{\"data_quality_score\": 0.55}",
            "return_1d": "+1.00%",
            "return_5d": "+2.00%",
            "return_20d": "N/A",
            "evaluated_1d": "True",
            "evaluated_5d": "True",
            "evaluated_20d": "False",
            "barrier_label": "hit",
            "catalyst_tag": "earnings",
        },
        {
            "signal_date": "2026-04-29",
            "ticker": "MSFT",
            "action": "buy",
            "conviction": "72",
            "regime": "risk_on",
            "factors_json": "{\"momentum\": 1.4}",
            "confidence_meta_json": "{}",
            "return_1d": "+0.50%",
            "return_5d": "+3.00%",
            "return_20d": "+6.00%",
            "evaluated_1d": "True",
            "evaluated_5d": "True",
            "evaluated_20d": "True",
            "barrier_label": "hit",
            "catalyst_tag": "product",
        },
    ]
    payload = write_analysis_performance_output(
        output_root=output_root,
        run_date=date(2026, 5, 1),
        decisions=[
            TickerDecision(
                ticker="AAPL",
                action="buy",
                conviction=68,
                factors={"momentum": 1.2},
                confidence_meta={"data_quality_score": 0.80},
            )
        ],
        market_regime=MarketRegime(regime="risk_on"),
        signal_rows=signal_rows,
    )

shape = normalize_json_shape(payload)
Path("tests/fixtures/output_schemas/analysis_performance.shape.json").write_text(
    json.dumps(shape, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
'@ | python -
```

Expected: rewrites only `tests/fixtures/output_schemas/analysis_performance.shape.json`.

- [ ] **Step 6: Run output schema test**

Run:

```powershell
python -m pytest tests/test_output_schema.py::OutputSchemaTests::test_analysis_performance_json_matches_snapshot_shape -v
```

Expected: test passes.

- [ ] **Step 7: Commit output wiring**

Run:

```powershell
git add src/output/analysis_performance.py tests/test_analysis_performance_output.py tests/test_output_schema.py tests/fixtures/output_schemas/analysis_performance.shape.json
git commit -m "feat: include ai backtest in analysis performance output"
```

Expected: commit succeeds.

---

### Task 3: Output Health Validation

**Files:**
- Create: `src/output/health_analysis_performance_ai_backtest.py`
- Modify: `src/output/health_analysis_performance.py`
- Modify: `tests/test_output_health_check.py`

- [ ] **Step 1: Extend the valid health fixture**

In `tests/test_output_health_check.py`, inside `_valid_analysis_performance_payload()`, add this root key before the closing `}`:

```python
        "ai_recommendation_backtest": {
            "status": "ok",
            "basis": "final_action",
            "horizons": ["1d", "5d", "20d"],
            "summary": {
                "sample_count": 12,
                "completed_20d_count": 10,
                "best_action": "buy",
                "worst_action": "avoid",
                "notes": ["AI recommendation backtest is observational."],
            },
            "by_action": {
                "buy": {
                    "20d": {
                        "sample_count": 12,
                        "completed_count": 10,
                        "avg_return": 2.5,
                        "median_return": 1.2,
                        "win_rate": 0.7,
                        "loss_rate": 0.3,
                        "best_return": 8.0,
                        "worst_return": -4.0,
                        "missing_count": 2,
                    },
                },
            },
            "conviction_buckets": {
                "65_80": {
                    "sample_count": 12,
                    "action_counts": {"buy": 12},
                    "by_action": {
                        "buy": {
                            "20d": {
                                "sample_count": 12,
                                "completed_count": 10,
                                "avg_return": 2.5,
                                "median_return": 1.2,
                                "win_rate": 0.7,
                                "loss_rate": 0.3,
                                "best_return": 8.0,
                                "worst_return": -4.0,
                                "missing_count": 2,
                            },
                        },
                    },
                },
            },
            "ticker_leaderboard": [
                {
                    "ticker": "AAPL",
                    "signals": 12,
                    "buy_signals": 12,
                    "avoid_signals": 0,
                    "completed_5d_count": 10,
                    "completed_20d_count": 10,
                    "avg_return_5d": 2.0,
                    "avg_return_20d": 2.5,
                    "win_rate_5d": 0.7,
                    "win_rate_20d": 0.7,
                }
            ],
            "notable_examples": {
                "best": [
                    {
                        "signal_date": "2026-04-01",
                        "ticker": "AAPL",
                        "action": "buy",
                        "conviction": 72.0,
                        "return_5d": 4.0,
                        "return_20d": 8.0,
                        "catalyst_tag": "earnings",
                        "regime": "risk_on",
                    }
                ],
                "worst": [],
            },
        },
```

- [ ] **Step 2: Add malformed AI backtest health tests**

In `tests/test_output_health_check.py`, near the existing invalid analysis performance tests, add:

```python
    def test_detects_invalid_ai_recommendation_backtest_shape(self) -> None:
        mutations = [
            ("basis", lambda payload: payload["ai_recommendation_backtest"].update({"basis": "llm_direction"})),
            ("horizons", lambda payload: payload["ai_recommendation_backtest"].update({"horizons": "20d"})),
            ("completed_20d_count", lambda payload: payload["ai_recommendation_backtest"]["summary"].update({"completed_20d_count": -1})),
            ("win_rate", lambda payload: payload["ai_recommendation_backtest"]["by_action"]["buy"]["20d"].update({"win_rate": 1.2})),
            ("ticker_leaderboard", lambda payload: payload["ai_recommendation_backtest"].update({"ticker_leaderboard": {}})),
            ("notable_examples", lambda payload: payload["ai_recommendation_backtest"].update({"notable_examples": []})),
        ]
        for field, mutate in mutations:
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    payload = _valid_analysis_performance_payload()
                    mutate(payload)
                    _write_json(root / "output" / "data" / "analysis_performance.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "analysis_performance.json", payload)

                    result = check_output_health(root)

                self.assertTrue(
                    any(
                        issue.code == "invalid_analysis_performance" and field in issue.detail
                        for issue in result.issues
                    ),
                    result.issues,
                )
```

- [ ] **Step 3: Run health test and verify it fails**

Run:

```powershell
python -m pytest tests/test_output_health_check.py -k ai_recommendation_backtest -v
```

Expected: fails because AI backtest validation is not implemented.

- [ ] **Step 4: Create the AI backtest health validator**

Create `src/output/health_analysis_performance_ai_backtest.py`:

```python
"""Health checks for AI recommendation backtest analytics."""

from __future__ import annotations

from pathlib import Path

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_int_mapping,
    _is_number_or_none,
    _is_probability_or_none,
    _is_string_list,
)


def _validate_ai_recommendation_backtest(path: Path, payload: dict) -> OutputHealthIssue | None:
    backtest = payload.get("ai_recommendation_backtest")
    if backtest is None:
        return None
    required = {"status", "basis", "horizons", "summary", "by_action", "conviction_buckets", "ticker_leaderboard", "notable_examples"}
    if not isinstance(backtest, dict) or not required.issubset(backtest.keys()):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "ai_recommendation_backtest missing status/basis/horizons/summary/by_action/conviction_buckets/ticker_leaderboard/notable_examples",
        )
    if not isinstance(backtest.get("status"), str) or not backtest.get("status", "").strip():
        return OutputHealthIssue("invalid_analysis_performance", str(path), "status must be a non-empty string for ai_recommendation_backtest")
    if backtest.get("basis") != "final_action":
        return OutputHealthIssue("invalid_analysis_performance", str(path), "basis must be final_action for ai_recommendation_backtest")
    if not _is_string_list(backtest.get("horizons")):
        return OutputHealthIssue("invalid_analysis_performance", str(path), "horizons must be a string list for ai_recommendation_backtest")

    issue = _validate_ai_summary(path, backtest.get("summary"))
    if issue is not None:
        return issue
    issue = _validate_ai_by_action(path, "ai_recommendation_backtest by_action", backtest.get("by_action"))
    if issue is not None:
        return issue
    issue = _validate_ai_conviction_buckets(path, backtest.get("conviction_buckets"))
    if issue is not None:
        return issue
    issue = _validate_ai_ticker_leaderboard(path, backtest.get("ticker_leaderboard"))
    if issue is not None:
        return issue
    return _validate_ai_examples(path, backtest.get("notable_examples"))


def _validate_ai_summary(path: Path, summary: object) -> OutputHealthIssue | None:
    required = {"sample_count", "completed_20d_count", "best_action", "worst_action", "notes"}
    if not isinstance(summary, dict) or not required.issubset(summary.keys()):
        return OutputHealthIssue("invalid_analysis_performance", str(path), "summary missing fields for ai_recommendation_backtest")
    for field in ("sample_count", "completed_20d_count"):
        if not _is_non_negative_int(summary.get(field)):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"{field} must be a non-negative integer for ai_recommendation_backtest summary")
    for field in ("best_action", "worst_action"):
        value = summary.get(field)
        if value is not None and not isinstance(value, str):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"{field} must be a string or null for ai_recommendation_backtest summary")
    if not _is_string_list(summary.get("notes")):
        return OutputHealthIssue("invalid_analysis_performance", str(path), "notes must be a string list for ai_recommendation_backtest summary")
    return None


def _validate_ai_by_action(path: Path, label: str, mapping: object) -> OutputHealthIssue | None:
    if not isinstance(mapping, dict):
        return OutputHealthIssue("invalid_analysis_performance", str(path), f"{label} must be an object")
    for action, by_horizon in mapping.items():
        if not isinstance(action, str) or not action.strip():
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"{label} keys must be non-empty strings")
        if not isinstance(by_horizon, dict):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"{label} {action} must be a horizon object")
        for horizon, stats in by_horizon.items():
            if not isinstance(horizon, str) or not horizon.strip():
                return OutputHealthIssue("invalid_analysis_performance", str(path), f"{label} {action} horizon keys must be non-empty strings")
            issue = _validate_ai_window_stats(path, f"{label} {action}/{horizon}", stats)
            if issue is not None:
                return issue
    return None


def _validate_ai_window_stats(path: Path, label: str, stats: object) -> OutputHealthIssue | None:
    count_fields = ("sample_count", "completed_count", "missing_count")
    number_fields = ("avg_return", "median_return", "best_return", "worst_return")
    rate_fields = ("win_rate", "loss_rate")
    required = {*count_fields, *number_fields, *rate_fields}
    if not isinstance(stats, dict) or not required.issubset(stats.keys()):
        return OutputHealthIssue("invalid_analysis_performance", str(path), f"{label} missing ai recommendation window stats fields")
    for field in count_fields:
        if not _is_non_negative_int(stats.get(field)):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"{field} must be a non-negative integer for {label}")
    for field in number_fields:
        if not _is_number_or_none(stats.get(field)):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"{field} must be a number or null for {label}")
    for field in rate_fields:
        if not _is_probability_or_none(stats.get(field)):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"{field} must be a number from 0 to 1 or null for {label}")
    return None


def _validate_ai_conviction_buckets(path: Path, buckets: object) -> OutputHealthIssue | None:
    if not isinstance(buckets, dict):
        return OutputHealthIssue("invalid_analysis_performance", str(path), "conviction_buckets must be an object for ai_recommendation_backtest")
    for bucket, stats in buckets.items():
        if not isinstance(bucket, str) or not bucket.strip():
            return OutputHealthIssue("invalid_analysis_performance", str(path), "conviction_buckets keys must be non-empty strings for ai_recommendation_backtest")
        required = {"sample_count", "action_counts", "by_action"}
        if not isinstance(stats, dict) or not required.issubset(stats.keys()):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"conviction bucket {bucket} missing fields for ai_recommendation_backtest")
        if not _is_non_negative_int(stats.get("sample_count")):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"sample_count must be a non-negative integer for ai recommendation conviction bucket {bucket}")
        if not _is_non_negative_int_mapping(stats.get("action_counts")):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"action_counts must be non-negative integer counts for ai recommendation conviction bucket {bucket}")
        issue = _validate_ai_by_action(path, f"ai_recommendation_backtest conviction_buckets {bucket}", stats.get("by_action"))
        if issue is not None:
            return issue
    return None


def _validate_ai_ticker_leaderboard(path: Path, rows: object) -> OutputHealthIssue | None:
    if not isinstance(rows, list):
        return OutputHealthIssue("invalid_analysis_performance", str(path), "ticker_leaderboard must be a list for ai_recommendation_backtest")
    required = {"ticker", "signals", "buy_signals", "avoid_signals", "completed_5d_count", "completed_20d_count", "avg_return_5d", "avg_return_20d", "win_rate_5d", "win_rate_20d"}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not required.issubset(row.keys()):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"ticker_leaderboard item {index} missing fields for ai_recommendation_backtest")
        if not isinstance(row.get("ticker"), str) or not row.get("ticker", "").strip():
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"ticker must be a non-empty string for ticker_leaderboard item {index}")
        for field in ("signals", "buy_signals", "avoid_signals", "completed_5d_count", "completed_20d_count"):
            if not _is_non_negative_int(row.get(field)):
                return OutputHealthIssue("invalid_analysis_performance", str(path), f"{field} must be a non-negative integer for ticker_leaderboard item {index}")
        for field in ("avg_return_5d", "avg_return_20d"):
            if not _is_number_or_none(row.get(field)):
                return OutputHealthIssue("invalid_analysis_performance", str(path), f"{field} must be a number or null for ticker_leaderboard item {index}")
        for field in ("win_rate_5d", "win_rate_20d"):
            if not _is_probability_or_none(row.get(field)):
                return OutputHealthIssue("invalid_analysis_performance", str(path), f"{field} must be a number from 0 to 1 or null for ticker_leaderboard item {index}")
    return None


def _validate_ai_examples(path: Path, examples: object) -> OutputHealthIssue | None:
    if not isinstance(examples, dict) or not {"best", "worst"}.issubset(examples.keys()):
        return OutputHealthIssue("invalid_analysis_performance", str(path), "notable_examples must include best/worst for ai_recommendation_backtest")
    for field in ("best", "worst"):
        rows = examples.get(field)
        if not isinstance(rows, list):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"notable_examples.{field} must be a list for ai_recommendation_backtest")
        for index, row in enumerate(rows):
            issue = _validate_ai_example(path, f"notable_examples.{field}[{index}]", row)
            if issue is not None:
                return issue
    return None


def _validate_ai_example(path: Path, label: str, row: object) -> OutputHealthIssue | None:
    required = {"signal_date", "ticker", "action", "conviction", "return_5d", "return_20d", "catalyst_tag", "regime"}
    if not isinstance(row, dict) or not required.issubset(row.keys()):
        return OutputHealthIssue("invalid_analysis_performance", str(path), f"{label} missing fields for ai_recommendation_backtest")
    for field in ("signal_date", "ticker", "action", "catalyst_tag", "regime"):
        if not isinstance(row.get(field), str):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"{field} must be a string for {label}")
    for field in ("conviction", "return_5d", "return_20d"):
        if not _is_number_or_none(row.get(field)):
            return OutputHealthIssue("invalid_analysis_performance", str(path), f"{field} must be a number or null for {label}")
    return None
```

- [ ] **Step 5: Wire the validator into analysis performance health checks**

In `src/output/health_analysis_performance.py`, add:

```python
from src.output.health_analysis_performance_ai_backtest import _validate_ai_recommendation_backtest
```

Then add `_validate_ai_recommendation_backtest` to the `validators` tuple after `_validate_analysis_performance_action_changes`:

```python
        _validate_analysis_performance_action_changes,
        _validate_ai_recommendation_backtest,
```

- [ ] **Step 6: Run health tests**

Run:

```powershell
python -m pytest tests/test_output_health_check.py -k "analysis_performance or ai_recommendation_backtest" -v
```

Expected: selected tests pass.

- [ ] **Step 7: Commit health validation**

Run:

```powershell
git add src/output/health_analysis_performance.py src/output/health_analysis_performance_ai_backtest.py tests/test_output_health_check.py
git commit -m "test: validate ai recommendation backtest output"
```

Expected: commit succeeds.

---

### Task 4: Frontend Types And AI Backtest Panel

**Files:**
- Modify: `web/src/types/index.ts`
- Create: `web/src/components/AiRecommendationBacktestPanel.tsx`
- Modify: `web/src/pages/Backtest.tsx`
- Modify: `web/src/pages/BacktestAnalysisPerformance.test.tsx`

- [ ] **Step 1: Add TypeScript payload interfaces**

In `web/src/types/index.ts`, add these interfaces after `AnalysisPerformanceActionChange`:

```ts
export interface AiRecommendationWindowStats {
  sample_count: number
  completed_count: number
  avg_return: number | null
  median_return: number | null
  win_rate: number | null
  loss_rate: number | null
  best_return: number | null
  worst_return: number | null
  missing_count: number
}

export interface AiRecommendationConvictionBucket {
  sample_count: number
  action_counts: Record<string, number>
  by_action: Record<string, Record<string, AiRecommendationWindowStats>>
}

export interface AiRecommendationTickerRow {
  ticker: string
  signals: number
  buy_signals: number
  avoid_signals: number
  completed_5d_count: number
  completed_20d_count: number
  avg_return_5d: number | null
  avg_return_20d: number | null
  win_rate_5d: number | null
  win_rate_20d: number | null
}

export interface AiRecommendationExample {
  signal_date: string
  ticker: string
  action: string
  conviction: number | null
  return_5d: number | null
  return_20d: number | null
  catalyst_tag: string
  regime: string
}

export interface AiRecommendationBacktestPayload {
  status: string
  basis: 'final_action' | string
  horizons: string[]
  summary: {
    sample_count: number
    completed_20d_count: number
    best_action: string | null
    worst_action: string | null
    notes: string[]
  }
  by_action: Record<string, Record<string, AiRecommendationWindowStats>>
  conviction_buckets: Record<string, AiRecommendationConvictionBucket>
  ticker_leaderboard: AiRecommendationTickerRow[]
  notable_examples: {
    best: AiRecommendationExample[]
    worst: AiRecommendationExample[]
  }
}
```

Then add this optional field to `AnalysisPerformancePayload`:

```ts
  ai_recommendation_backtest?: AiRecommendationBacktestPayload
```

- [ ] **Step 2: Create the panel component**

Create `web/src/components/AiRecommendationBacktestPanel.tsx`:

```tsx
import type {
  AiRecommendationBacktestPayload,
  AiRecommendationExample,
  AiRecommendationWindowStats,
} from '../types'

export function AiRecommendationBacktestPanel({ payload }: { payload?: AiRecommendationBacktestPayload | null }) {
  if (!payload) return null

  if (payload.status !== 'ok') {
    return (
      <section className="signals-meta-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>AI 추천 백테스팅</h3>
            <p className="section-kicker">최종 buy / watch / avoid 판단이 이후 1일, 5일, 20일 수익률과 얼마나 맞았는지 추적합니다.</p>
          </div>
        </div>
        <div className="detail-note-card">
          <p>평가 기간이 더 쌓이면 AI 추천 백테스팅이 표시됩니다.</p>
        </div>
      </section>
    )
  }

  const buy20 = payload.by_action.buy?.['20d'] ?? null
  const avoid20 = payload.by_action.avoid?.['20d'] ?? null
  const highConvictionBuy = pickHighConvictionBuy(payload)
  const rows = ['buy', 'watch', 'avoid']

  return (
    <section className="signals-meta-section ai-backtest-panel">
      <div className="section-header-with-kicker">
        <div>
          <h3>AI 추천 백테스팅</h3>
          <p className="section-kicker">최종 buy / watch / avoid 판단이 이후 1일, 5일, 20일 수익률과 얼마나 맞았는지 추적합니다.</p>
        </div>
        <span className="period-badge ap-mode-badge">Final action</span>
      </div>

      <div className="signal-summary-grid">
        <SummaryCard
          label="BUY 추천 승률"
          value={formatRatio(buy20?.win_rate)}
          note={`20D 평균 ${formatPercent(buy20?.avg_return)} · ${buy20?.completed_count ?? 0}/${buy20?.sample_count ?? 0}건`}
        />
        <SummaryCard
          label="고확신 BUY"
          value={formatPercent(highConvictionBuy?.avg_return)}
          note={`20D 승률 ${formatRatio(highConvictionBuy?.win_rate)} · ${highConvictionBuy?.completed_count ?? 0}건`}
        />
        <SummaryCard
          label="AVOID 방어 성공률"
          value={formatRatio(avoid20?.win_rate)}
          note={`20D 평균 ${formatPercent(avoid20?.avg_return)} · ${avoid20?.completed_count ?? 0}/${avoid20?.sample_count ?? 0}건`}
        />
        <SummaryCard
          label="평가 완료"
          value={`${payload.summary.completed_20d_count}`}
          note={`전체 추천 ${payload.summary.sample_count}건 중 20D 완료`}
        />
      </div>

      <div className="watchlist-table-shell">
        <table className="watchlist-table ap-table">
          <thead>
            <tr>
              <th>추천</th>
              <th className="ap-num">1D 평균</th>
              <th className="ap-num">5D 평균</th>
              <th className="ap-num">20D 평균</th>
              <th className="ap-num">20D 승률</th>
              <th className="ap-num">표본</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((action) => {
              const oneDay = payload.by_action[action]?.['1d'] ?? null
              const fiveDay = payload.by_action[action]?.['5d'] ?? null
              const twentyDay = payload.by_action[action]?.['20d'] ?? null
              return (
                <tr key={action}>
                  <td className="ap-factor-name">{action.toUpperCase()}</td>
                  <td className="ap-num">{formatPercent(oneDay?.avg_return)}</td>
                  <td className="ap-num">{formatPercent(fiveDay?.avg_return)}</td>
                  <td className="ap-num">{formatPercent(twentyDay?.avg_return)}</td>
                  <td className="ap-num">{formatRatio(twentyDay?.win_rate)}</td>
                  <td className="ap-num">{twentyDay?.completed_count ?? 0}/{twentyDay?.sample_count ?? 0}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="signal-summary-grid">
        <ExampleTable title="잘 맞은 추천" rows={payload.notable_examples.best} />
        <ExampleTable title="틀린 추천" rows={payload.notable_examples.worst} />
      </div>

      <p className="section-kicker ap-footnote">
        이 지표는 사후 검증용이며 공식 투자 판단이나 다음 실행 로직을 변경하지 않습니다.
      </p>
    </section>
  )
}

function SummaryCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="signal-summary-card ap-summary-card">
      <div className="signal-summary-direction">{label}</div>
      <div className="signal-summary-count ap-summary-value">{value}</div>
      <div className="ap-summary-note">{note}</div>
    </div>
  )
}

function ExampleTable({ title, rows }: { title: string; rows: AiRecommendationExample[] }) {
  return (
    <div className="watchlist-table-shell">
      <h4 className="ap-table-heading">{title}</h4>
      <table className="watchlist-table ap-table">
        <thead>
          <tr>
            <th>날짜</th>
            <th>티커</th>
            <th>추천</th>
            <th className="ap-num">확신</th>
            <th className="ap-num">20D</th>
          </tr>
        </thead>
        <tbody>
          {rows.length > 0 ? rows.map((row) => (
            <tr key={`${title}-${row.signal_date}-${row.ticker}-${row.action}`}>
              <td>{row.signal_date}</td>
              <td className="ap-ticker">{row.ticker}</td>
              <td>{row.action.toUpperCase()}</td>
              <td className="ap-num">{formatNumber(row.conviction)}</td>
              <td className="ap-num">{formatPercent(row.return_20d)}</td>
            </tr>
          )) : (
            <tr>
              <td colSpan={5}>평가된 추천 샘플이 아직 없습니다.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function pickHighConvictionBuy(payload: AiRecommendationBacktestPayload): AiRecommendationWindowStats | null {
  return payload.conviction_buckets['80_100']?.by_action.buy?.['20d']
    ?? payload.conviction_buckets['65_80']?.by_action.buy?.['20d']
    ?? null
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return `${(value * 100).toFixed(1)}%`
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
  return value.toFixed(0)
}
```

- [ ] **Step 3: Render the panel on the Backtest page**

In `web/src/pages/Backtest.tsx`, add:

```ts
import { AiRecommendationBacktestPanel } from '../components/AiRecommendationBacktestPanel'
```

Then render after the existing `AnalysisPerformancePanel`:

```tsx
      <AnalysisPerformancePanel payload={analysisPerformance} />
      <AiRecommendationBacktestPanel payload={analysisPerformance?.ai_recommendation_backtest} />
```

- [ ] **Step 4: Add frontend test payload and assertions**

In `web/src/pages/BacktestAnalysisPerformance.test.tsx`, add `ai_recommendation_backtest` to the mocked `analysis_performance.json` payload:

```ts
          ai_recommendation_backtest: {
            status: 'ok',
            basis: 'final_action',
            horizons: ['1d', '5d', '20d'],
            summary: {
              sample_count: 225,
              completed_20d_count: 90,
              best_action: 'buy',
              worst_action: 'avoid',
              notes: ['AI recommendation backtest is observational.'],
            },
            by_action: {
              buy: {
                '1d': { sample_count: 62, completed_count: 60, avg_return: 1.1, median_return: 0.8, win_rate: 0.65, loss_rate: 0.35, best_return: 8.0, worst_return: -3.0, missing_count: 2 },
                '5d': { sample_count: 62, completed_count: 45, avg_return: 4.7678, median_return: 3.61, win_rate: 0.7111, loss_rate: 0.2889, best_return: 18.0, worst_return: -8.0, missing_count: 17 },
                '20d': { sample_count: 62, completed_count: 40, avg_return: 6.25, median_return: 4.2, win_rate: 0.725, loss_rate: 0.275, best_return: 24.0, worst_return: -10.0, missing_count: 22 },
              },
              watch: {
                '1d': { sample_count: 139, completed_count: 130, avg_return: 0.2, median_return: 0.1, win_rate: null, loss_rate: null, best_return: 3.0, worst_return: -2.0, missing_count: 9 },
                '5d': { sample_count: 139, completed_count: 87, avg_return: 2.6582, median_return: 1.72, win_rate: null, loss_rate: null, best_return: 12.0, worst_return: -6.0, missing_count: 52 },
                '20d': { sample_count: 139, completed_count: 50, avg_return: 3.2, median_return: 1.9, win_rate: null, loss_rate: null, best_return: 20.0, worst_return: -12.0, missing_count: 89 },
              },
              avoid: {
                '1d': { sample_count: 24, completed_count: 22, avg_return: -0.4, median_return: -0.2, win_rate: 0.6, loss_rate: 0.4, best_return: 2.0, worst_return: -5.0, missing_count: 2 },
                '5d': { sample_count: 24, completed_count: 18, avg_return: -1.4, median_return: -0.8, win_rate: 0.6667, loss_rate: 0.3333, best_return: 4.0, worst_return: -9.0, missing_count: 6 },
                '20d': { sample_count: 24, completed_count: 12, avg_return: -2.5, median_return: -1.1, win_rate: 0.75, loss_rate: 0.25, best_return: 5.0, worst_return: -14.0, missing_count: 12 },
              },
            },
            conviction_buckets: {
              '80_100': {
                sample_count: 10,
                action_counts: { buy: 10 },
                by_action: {
                  buy: {
                    '20d': { sample_count: 10, completed_count: 8, avg_return: 9.5, median_return: 8.1, win_rate: 0.875, loss_rate: 0.125, best_return: 24.0, worst_return: -3.0, missing_count: 2 },
                  },
                },
              },
            },
            ticker_leaderboard: [],
            notable_examples: {
              best: [
                { signal_date: '2026-04-10', ticker: 'AMD', action: 'buy', conviction: 88, return_5d: 12.4, return_20d: 24.0, catalyst_tag: 'product', regime: 'risk_on' },
              ],
              worst: [
                { signal_date: '2026-04-12', ticker: 'AAPL', action: 'buy', conviction: 72, return_5d: -4.0, return_20d: -10.0, catalyst_tag: 'earnings', regime: 'neutral' },
              ],
            },
          },
```

Add assertions to the existing test:

```ts
    expect(screen.getByRole('heading', { name: 'AI 추천 백테스팅' })).toBeInTheDocument()
    expect(screen.getByText('BUY 추천 승률')).toBeInTheDocument()
    expect(screen.getByText('72.5%')).toBeInTheDocument()
    expect(screen.getByText('고확신 BUY')).toBeInTheDocument()
    expect(screen.getByText('+9.50%')).toBeInTheDocument()
    expect(screen.getByText('AVOID 방어 성공률')).toBeInTheDocument()
    expect(screen.getByText('75.0%')).toBeInTheDocument()
    expect(screen.getByText('잘 맞은 추천')).toBeInTheDocument()
    expect(screen.getByText('틀린 추천')).toBeInTheDocument()
```

- [ ] **Step 5: Run frontend test and verify it fails before component wiring if skipped**

Run:

```powershell
npm --prefix web test -- BacktestAnalysisPerformance
```

Expected after Steps 1-4: pass. Expected if the panel import/render step was skipped: fail because `AI 추천 백테스팅` is missing.

- [ ] **Step 6: Run TypeScript check**

Run:

```powershell
npm --prefix web run typecheck
```

Expected: typecheck passes.

- [ ] **Step 7: Commit frontend rendering**

Run:

```powershell
git add web/src/types/index.ts web/src/components/AiRecommendationBacktestPanel.tsx web/src/pages/Backtest.tsx web/src/pages/BacktestAnalysisPerformance.test.tsx
git commit -m "feat: render ai recommendation backtest panel"
```

Expected: commit succeeds.

---

### Task 5: Documentation, Generated Artifact Refresh, And Final Verification

**Files:**
- Modify: `docs/output.md`
- Modify after regeneration: `output/data/analysis_performance.json`
- Modify after regeneration: `web/public/output/data/analysis_performance.json`

- [ ] **Step 1: Update output documentation**

In `docs/output.md`, under `### Analysis Performance Outputs`, add this paragraph after the existing description of `analysis_performance.json`:

```markdown
`analysis_performance.json.ai_recommendation_backtest` is an additive read-only AI recommendation backtest block. It evaluates finalized `buy` / `watch` / `avoid` actions from `signal_tracker.csv` against realized 1d, 5d, and 20d returns, high-conviction buckets, ticker-level outcomes, and best/worst examples. The block uses `basis: "final_action"` in v1, is observational only, and must not recompute or override official decisions, model routing, factor weights, or execution behavior.
```

- [ ] **Step 2: Regenerate analysis performance output from existing artifacts**

Run:

```powershell
python -m src.cli.write_performance_outputs --project-root .
```

Expected: performance artifacts are rewritten from existing generated outputs without rerunning collection, analysis, or decision logic. `output/data/analysis_performance.json` and `web/public/output/data/analysis_performance.json` include `ai_recommendation_backtest`.

- [ ] **Step 3: Verify output health**

Run:

```powershell
python -m src.cli.output_health_check
```

Expected: no `invalid_analysis_performance` issues. If pre-existing mirror mismatch issues remain from earlier generated output state, copy the source `output/data` files into matching `web/public/output/data` mirror paths and rerun this command.

- [ ] **Step 4: Run backend verification suite**

Run:

```powershell
python -m pytest tests/test_performance_analytics.py tests/test_analysis_performance_output.py tests/test_output_schema.py tests/test_output_health_check.py -v
```

Expected: all selected backend tests pass.

- [ ] **Step 5: Run frontend verification suite**

Run:

```powershell
npm --prefix web test -- BacktestAnalysisPerformance
npm --prefix web run typecheck
```

Expected: Backtest test and typecheck pass.

- [ ] **Step 6: Inspect final working tree**

Run:

```powershell
git status --short --branch
```

Expected: only intended implementation, docs, tests, fixture, and generated artifact files are modified.

- [ ] **Step 7: Commit documentation and generated outputs**

Run:

```powershell
git add docs/output.md output/data/analysis_performance.json web/public/output/data/analysis_performance.json
git commit -m "docs: document ai recommendation backtest output"
```

Expected: commit succeeds.

- [ ] **Step 8: Final implementation commit check**

Run:

```powershell
git log --oneline --max-count=5
git status --short --branch
```

Expected: recent commits include the AI backtest implementation commits, and the branch has no unintended unstaged changes.
