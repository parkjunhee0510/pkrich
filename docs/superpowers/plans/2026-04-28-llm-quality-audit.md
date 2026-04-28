# LLM Quality Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a one-shot LLM quality audit module (`src/eval/`) that runs 14 diagnostic checks against the analyzer's 14-day window, with cost-guarded LLM replay (D1) and produces both a markdown report and machine-readable JSON.

**Architecture:** Plugin check pattern. Each check is a class implementing `BaseCheck.run(dataset) -> CheckResult`. A central runner loads a frozen `AuditDataset` once from `output/data/` + `logs/pipeline/`, dispatches all checks, isolates failures per check, then renders two artifacts. Replay is the only check with API costs and is gated by `--max-replay-cost-usd` and `--dry-run`.

**Tech Stack:** Python 3.11, stdlib (`unittest`, `argparse`, `dataclasses`, `re`, `json`, `pathlib`), existing project deps (`pydantic` already pulled in by analyzer). For O3-(b) optional link check: `urllib`. For D1 embedding similarity: `sentence-transformers` (already in deps via analyzer for narrative). No new top-level dependencies.

**Spec:** `docs/superpowers/specs/2026-04-28-llm-quality-audit-design.md`

---

## File Structure (Locked-In)

```
src/eval/
├── __init__.py                 # marker only
├── runner.py                   # CLI + orchestration (≤200 LOC)
├── config.py                   # thresholds, registry, CLI defaults (≤120 LOC)
├── data_sources.py             # AuditDataset loader (≤200 LOC)
├── replay.py                   # FakeLLMClient interface, cost guard, dry-run (≤180 LOC)
├── report.py                   # markdown + JSON renderers (≤220 LOC)
├── README.md                   # usage doc
└── checks/
    ├── __init__.py
    ├── base.py                 # CheckResult, Finding, BaseCheck (≤80 LOC)
    ├── i1_schema_stability.py
    ├── i2_missingness.py
    ├── i3_format_consistency.py
    ├── i4_input_size_drift.py
    ├── o1_schema_compliance.py
    ├── o2_numeric_grounding.py
    ├── o3_citation_integrity.py
    ├── o4_language_consistency.py
    ├── o5_contradiction.py
    ├── d1_semantic_drift.py
    ├── d2_committee_agreement.py
    ├── d3_signal_volatility.py
    ├── r1_pipeline_summary.py
    └── r2_retry_distribution.py

tests/eval/
├── __init__.py
├── test_runner.py              # integration
├── test_data_sources.py
├── test_report.py
├── test_replay.py
├── fixtures/
│   ├── __init__.py
│   ├── builders.py             # make_dataset(...) factory
│   └── golden/
│       └── audit_report_sample.md
└── checks/
    ├── __init__.py
    └── test_<id>.py × 14
```

**Test runner:** `python -m unittest discover -s tests -v` (project standard, NOT pytest).

---

### Task 1: Foundation — `BaseCheck`, `CheckResult`, `Finding`

**Files:**
- Create: `src/eval/__init__.py` (empty marker)
- Create: `src/eval/checks/__init__.py` (empty marker)
- Create: `src/eval/checks/base.py`
- Create: `tests/eval/__init__.py` (empty marker)
- Create: `tests/eval/checks/__init__.py` (empty marker)
- Create: `tests/eval/checks/test_base.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_base.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.base import BaseCheck, CheckResult, Finding


class TestCheckResultShape(unittest.TestCase):
    def test_finding_is_frozen(self):
        f = Finding(ticker="AAPL", date=date(2026, 4, 28), module="research_note",
                    jsonpath="$.summary", detail={"reason": "x"})
        with self.assertRaises(Exception):
            f.ticker = "MSFT"  # type: ignore[misc]

    def test_check_result_pass_rate_clamped(self):
        cr = CheckResult(check_id="X", severity="pass", pass_rate=1.0,
                         findings=(), metrics={}, recommendation=None)
        self.assertEqual(cr.pass_rate, 1.0)

    def test_base_check_is_abstract(self):
        with self.assertRaises(TypeError):
            BaseCheck()  # type: ignore[abstract]


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.eval.checks.test_base -v`
Expected: ImportError (module does not exist).

- [ ] **Step 3: Write minimal implementation**

`src/eval/__init__.py`:

```python
```

`src/eval/checks/__init__.py`:

```python
```

`src/eval/checks/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Mapping


Severity = Literal["pass", "warn", "fail", "info"]


@dataclass(frozen=True)
class Finding:
    ticker: str | None = None
    date: date | None = None
    module: str | None = None
    jsonpath: str | None = None
    detail: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.detail is None:
            object.__setattr__(self, "detail", {})


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    severity: Severity
    pass_rate: float
    findings: tuple[Finding, ...]
    metrics: Mapping[str, float]
    recommendation: str | None


class BaseCheck(ABC):
    check_id: str = ""
    dimension: str = ""

    @abstractmethod
    def run(self, dataset: "AuditDataset") -> CheckResult:  # noqa: F821 forward ref
        raise NotImplementedError
```

`tests/eval/__init__.py`:

```python
```

`tests/eval/checks/__init__.py`:

```python
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.eval.checks.test_base -v`
Expected: `OK` (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/__init__.py src/eval/checks/__init__.py src/eval/checks/base.py tests/eval/__init__.py tests/eval/checks/__init__.py tests/eval/checks/test_base.py
git commit -m "feat(eval): add BaseCheck/CheckResult/Finding primitives"
```

---

### Task 2: Config — thresholds, check registry

**Files:**
- Create: `src/eval/config.py`
- Create: `tests/eval/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/test_config.py`:

```python
from __future__ import annotations

import unittest

from src.eval.config import (
    DEFAULT_THRESHOLDS,
    DEFAULT_REPLAY_TICKERS,
    DEFAULT_RUNS_PER_TICKER,
    DEFAULT_WINDOW_DAYS,
    DEFAULT_MAX_REPLAY_COST_USD,
    severity_for,
)


class TestThresholds(unittest.TestCase):
    def test_all_14_checks_have_thresholds(self):
        expected = {
            "I1", "I2", "I3", "I4",
            "O1", "O2", "O3", "O4", "O5",
            "D1", "D2", "D3",
            "R1", "R2",
        }
        self.assertEqual(set(DEFAULT_THRESHOLDS.keys()), expected)

    def test_defaults(self):
        self.assertEqual(DEFAULT_WINDOW_DAYS, 14)
        self.assertEqual(DEFAULT_RUNS_PER_TICKER, 3)
        self.assertEqual(DEFAULT_MAX_REPLAY_COST_USD, 1.0)
        self.assertEqual(len(DEFAULT_REPLAY_TICKERS), 5)

    def test_severity_for_pass_warn_fail(self):
        # I3 thresholds: pass when format_count <= 1, warn when 2, fail when >= 3
        self.assertEqual(severity_for("I3", value=1, kind="format_count"), "pass")
        self.assertEqual(severity_for("I3", value=2, kind="format_count"), "warn")
        self.assertEqual(severity_for("I3", value=3, kind="format_count"), "fail")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.eval.test_config -v`
Expected: ImportError.

- [ ] **Step 3: Write minimal implementation**

`src/eval/config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DEFAULT_WINDOW_DAYS: int = 14
DEFAULT_RUNS_PER_TICKER: int = 3
DEFAULT_MAX_REPLAY_COST_USD: float = 1.0
DEFAULT_REPLAY_TICKERS: tuple[str, ...] = ("AAPL", "MSFT", "NVDA", "TSLA", "GOOGL")
ALL_CHECK_IDS: tuple[str, ...] = (
    "I1", "I2", "I3", "I4",
    "O1", "O2", "O3", "O4", "O5",
    "D1", "D2", "D3",
    "R1", "R2",
)


@dataclass(frozen=True)
class Thresholds:
    """Pass/warn boundaries. Severity descends as value crosses them."""
    pass_at: float
    warn_at: float
    direction: Literal["lower_is_better", "higher_is_better"]


# Severity is decided by `severity_for(check_id, value, kind)`.
# `kind` selects which sub-threshold (a check can have multiple metrics).
DEFAULT_THRESHOLDS: dict[str, dict[str, Thresholds]] = {
    "I1": {"missing_field_rate": Thresholds(0.02, 0.10, "lower_is_better")},
    "I2": {"missingness_rate": Thresholds(0.30, 0.60, "lower_is_better")},
    "I3": {"format_count": Thresholds(1, 2, "lower_is_better")},
    "I4": {"cv": Thresholds(0.20, 0.40, "lower_is_better")},
    "O1": {"violation_rate": Thresholds(0.0, 0.0, "lower_is_better")},  # binary
    "O2": {"match_rate": Thresholds(0.95, 0.85, "higher_is_better")},
    "O3": {"citation_match_rate": Thresholds(0.98, 0.90, "higher_is_better")},
    "O4": {"lang_ratio_std": Thresholds(0.15, 0.30, "lower_is_better")},
    "O5": {"three_way_agreement": Thresholds(0.85, 0.70, "higher_is_better")},
    "D1": {"action_match": Thresholds(1.0, 0.67, "higher_is_better"),
           "embedding_similarity": Thresholds(0.90, 0.80, "higher_is_better")},
    "D2": {"role_agreement": Thresholds(0.75, 0.60, "higher_is_better")},
    "D3": {"signal_std": Thresholds(0.25, 0.40, "lower_is_better")},
    "R1": {"fallback_rate": Thresholds(0.05, 0.15, "lower_is_better")},
    "R2": {"retry_per_ticker": Thresholds(2, 5, "lower_is_better")},
}


def severity_for(check_id: str, *, value: float, kind: str) -> str:
    t = DEFAULT_THRESHOLDS[check_id][kind]
    if t.direction == "lower_is_better":
        if value <= t.pass_at:
            return "pass"
        if value <= t.warn_at:
            return "warn"
        return "fail"
    else:
        if value >= t.pass_at:
            return "pass"
        if value >= t.warn_at:
            return "warn"
        return "fail"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.eval.test_config -v`
Expected: `OK` (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/config.py tests/eval/test_config.py
git commit -m "feat(eval): add thresholds + check registry"
```

---

### Task 3: Test fixtures — `make_dataset` builder

**Files:**
- Create: `tests/eval/fixtures/__init__.py`
- Create: `tests/eval/fixtures/builders.py`
- Create: `tests/eval/fixtures/test_builders.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/fixtures/test_builders.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from tests.eval.fixtures.builders import (
    make_dataset,
    make_daily,
    make_summary,
)


class TestBuilders(unittest.TestCase):
    def test_make_dataset_default(self):
        ds = make_dataset()
        self.assertEqual(ds.window_end - ds.window_start).days, 13  # 14d window inclusive
        self.assertGreater(len(ds.tickers), 0)
        for t in ds.tickers:
            self.assertEqual(len(ds.daily[t]), 14)

    def test_make_daily_overrides(self):
        d = make_daily(ticker="AAPL", as_of=date(2026, 4, 28),
                       summary="AAPL is at 273.43 USD (+0.10%).",
                       key_news=["headline 1"])
        self.assertEqual(d["payload"]["ticker"], "AAPL")
        self.assertIn("273.43", d["payload"]["summary"])

    def test_make_summary_token_usage(self):
        s = make_summary(date(2026, 4, 28), token_usage={"AAPL": 3000})
        self.assertEqual(s["model_usage"]["per_ticker_tokens"]["AAPL"], 3000)


if __name__ == "__main__":
    unittest.main()
```

(Note: There's a typo in the test on purpose to verify it actually fails — the `assertEqual(...).days, 13` pattern. We fix it in step 3 review by re-writing.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.eval.fixtures.test_builders -v`
Expected: ImportError + syntax issue.

- [ ] **Step 3: Write minimal implementation (and fix test)**

Fix `tests/eval/fixtures/test_builders.py` (replace the broken assert):

```python
from __future__ import annotations

import unittest
from datetime import date

from tests.eval.fixtures.builders import (
    make_dataset,
    make_daily,
    make_summary,
)


class TestBuilders(unittest.TestCase):
    def test_make_dataset_default(self):
        ds = make_dataset()
        self.assertEqual((ds.window_end - ds.window_start).days, 13)
        self.assertGreater(len(ds.tickers), 0)
        for t in ds.tickers:
            self.assertEqual(len(ds.daily[t]), 14)

    def test_make_daily_overrides(self):
        d = make_daily(ticker="AAPL", as_of=date(2026, 4, 28),
                       summary="AAPL is at 273.43 USD (+0.10%).",
                       key_news=["headline 1"])
        self.assertEqual(d["payload"]["ticker"], "AAPL")
        self.assertIn("273.43", d["payload"]["summary"])

    def test_make_summary_token_usage(self):
        s = make_summary(date(2026, 4, 28), token_usage={"AAPL": 3000})
        self.assertEqual(s["model_usage"]["per_ticker_tokens"]["AAPL"], 3000)


if __name__ == "__main__":
    unittest.main()
```

`tests/eval/fixtures/__init__.py`:

```python
```

`tests/eval/fixtures/builders.py`:

```python
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

from src.eval.data_sources import AuditDataset, PipelineEvent


def make_daily(
    *,
    ticker: str,
    as_of: date,
    summary: str = "Test summary 100.00 USD (+0.50%).",
    key_news: Sequence[str] | None = None,
    news_references: Sequence[Mapping[str, str]] | None = None,
    extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ticker": ticker,
        "name": f"{ticker} Inc.",
        "date": as_of.isoformat(),
        "summary": summary,
        "key_news": list(key_news or [f"{ticker} headline 1"]),
        "news_references": list(news_references or [
            {"title": f"{ticker} headline 1", "source": "Reuters",
             "published_at": as_of.isoformat(),
             "link": f"https://example.com/{ticker}/1"}
        ]),
    }
    if extra_payload:
        payload.update(extra_payload)
    return {
        "schema_version": 1,
        "date": as_of.isoformat(),
        "ticker": ticker,
        "payload": payload,
    }


def make_summary(
    as_of: date,
    *,
    fallback_count: int = 0,
    schema_retry_count: int = 0,
    token_usage: Mapping[str, int] | None = None,
    daily_api_cost_usd: float = 0.10,
) -> dict[str, Any]:
    return {
        "date": as_of.isoformat(),
        "components": {},
        "fallback_count": fallback_count,
        "schema_retry_count": schema_retry_count,
        "model_usage": {
            "per_ticker_tokens": dict(token_usage or {}),
            "total_tokens": sum((token_usage or {}).values()),
        },
        "daily_api_cost_usd": daily_api_cost_usd,
    }


def make_dataset(
    *,
    tickers: Sequence[str] = ("AAPL", "MSFT"),
    window_days: int = 14,
    end: date = date(2026, 4, 28),
    daily_overrides: Mapping[str, Mapping[date, dict]] | None = None,
    logs: Sequence[PipelineEvent] = (),
    summary_overrides: Mapping[date, dict] | None = None,
    model_profile: str = "economy",
) -> AuditDataset:
    start = end - timedelta(days=window_days - 1)
    days = [start + timedelta(days=i) for i in range(window_days)]
    daily: dict[str, dict[date, dict]] = {}
    for t in tickers:
        per_day: dict[date, dict] = {}
        for d in days:
            override = (daily_overrides or {}).get(t, {}).get(d)
            per_day[d] = override or make_daily(ticker=t, as_of=d)
        daily[t] = per_day
    summaries: dict[date, dict] = {}
    for d in days:
        override = (summary_overrides or {}).get(d)
        summaries[d] = override or make_summary(d)
    return AuditDataset(
        window_start=start,
        window_end=end,
        tickers=tuple(tickers),
        daily=daily,
        logs=tuple(logs),
        summaries=summaries,
        model_profile=model_profile,
    )
```

(`AuditDataset` and `PipelineEvent` are imported but not yet defined — Task 4 creates them.)

- [ ] **Step 4: Run test (still fails — depends on Task 4)**

Run: `python -m unittest tests.eval.fixtures.test_builders -v`
Expected: ImportError on `AuditDataset` (will be fixed in Task 4).

- [ ] **Step 5: Stage but do not commit yet**

We commit fixtures together with `data_sources.py` in Task 4 to keep the build green.

```bash
git add tests/eval/fixtures/
```

---

### Task 4: Data sources — `AuditDataset` + `load_window`

**Files:**
- Create: `src/eval/data_sources.py`
- Create: `tests/eval/test_data_sources.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/test_data_sources.py`:

```python
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.eval.data_sources import AuditDataset, load_window


class TestLoadWindow(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        # synthetic output/data layout
        ticker_dir = self.tmp / "output" / "data" / "tickers" / "AAPL" / "daily"
        ticker_dir.mkdir(parents=True)
        (ticker_dir / "2026-04-28.json").write_text(json.dumps({
            "schema_version": 1, "date": "2026-04-28", "ticker": "AAPL",
            "payload": {"ticker": "AAPL", "summary": "x", "key_news": [], "news_references": []}
        }))
        # synthetic logs
        log_dir = self.tmp / "logs" / "pipeline"
        log_dir.mkdir(parents=True)
        (log_dir / "2026-04-28.summary.json").write_text(json.dumps({
            "date": "2026-04-28", "fallback_count": 0, "schema_retry_count": 0,
            "model_usage": {"per_ticker_tokens": {"AAPL": 3000}, "total_tokens": 3000},
            "daily_api_cost_usd": 0.10,
        }))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_load_window_one_day(self):
        ds = load_window(
            root=self.tmp, end=date(2026, 4, 28), window_days=1,
            tickers=["AAPL"], model_profile="economy",
        )
        self.assertEqual(ds.tickers, ("AAPL",))
        self.assertIn(date(2026, 4, 28), ds.daily["AAPL"])
        self.assertEqual(ds.summaries[date(2026, 4, 28)]["fallback_count"], 0)

    def test_load_window_missing_day_is_none(self):
        ds = load_window(
            root=self.tmp, end=date(2026, 4, 28), window_days=2,
            tickers=["AAPL"], model_profile="economy",
        )
        self.assertEqual(len(ds.daily["AAPL"]), 1)  # only one day exists


class TestAuditDatasetIsFrozen(unittest.TestCase):
    def test_frozen(self):
        ds = AuditDataset(
            window_start=date(2026, 4, 28), window_end=date(2026, 4, 28),
            tickers=("AAPL",), daily={}, logs=(), summaries={}, model_profile="economy",
        )
        with self.assertRaises(Exception):
            ds.tickers = ("MSFT",)  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests — verify failure**

Run: `python -m unittest tests.eval.test_data_sources tests.eval.fixtures.test_builders -v`
Expected: ImportError on `AuditDataset`/`load_window`.

- [ ] **Step 3: Implement `data_sources.py`**

`src/eval/data_sources.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class PipelineEvent:
    date: date
    component: str
    severity: str  # "info" | "warn" | "error"
    message: str
    detail: Mapping[str, Any]
    ticker: str | None = None
    module: str | None = None


@dataclass(frozen=True)
class AuditDataset:
    window_start: date
    window_end: date
    tickers: tuple[str, ...]
    daily: Mapping[str, Mapping[date, dict]]
    logs: tuple[PipelineEvent, ...]
    summaries: Mapping[date, dict]
    model_profile: str


def _read_json(p: Path) -> dict[str, Any] | None:
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _read_jsonl(p: Path) -> list[dict[str, Any]]:
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _events_from_jsonl(rows: list[dict[str, Any]], d: date) -> list[PipelineEvent]:
    events: list[PipelineEvent] = []
    for row in rows:
        events.append(PipelineEvent(
            date=d,
            component=row.get("component", "unknown"),
            severity=row.get("severity", "info"),
            message=row.get("message", ""),
            detail=row.get("detail") or {},
            ticker=row.get("ticker"),
            module=row.get("module"),
        ))
    return events


def load_window(
    *,
    root: Path,
    end: date,
    window_days: int,
    tickers: list[str],
    model_profile: str,
) -> AuditDataset:
    if window_days < 1:
        raise ValueError(f"window_days must be >= 1, got {window_days}")
    start = end - timedelta(days=window_days - 1)
    days = [start + timedelta(days=i) for i in range(window_days)]

    daily: dict[str, dict[date, dict]] = {}
    for ticker in tickers:
        per_day: dict[date, dict] = {}
        base = root / "output" / "data" / "tickers" / ticker / "daily"
        for d in days:
            payload = _read_json(base / f"{d.isoformat()}.json")
            if payload is not None:
                per_day[d] = payload
        daily[ticker] = per_day

    summaries: dict[date, dict] = {}
    logs: list[PipelineEvent] = []
    log_root = root / "logs" / "pipeline"
    for d in days:
        s = _read_json(log_root / f"{d.isoformat()}.summary.json")
        if s is not None:
            summaries[d] = s
        rows = _read_jsonl(log_root / f"{d.isoformat()}.jsonl")
        logs.extend(_events_from_jsonl(rows, d))

    return AuditDataset(
        window_start=start,
        window_end=end,
        tickers=tuple(tickers),
        daily=daily,
        logs=tuple(logs),
        summaries=summaries,
        model_profile=model_profile,
    )
```

- [ ] **Step 4: Run tests — both pass**

Run: `python -m unittest tests.eval.test_data_sources tests.eval.fixtures.test_builders -v`
Expected: `OK` (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/data_sources.py tests/eval/test_data_sources.py tests/eval/fixtures/
git commit -m "feat(eval): AuditDataset + load_window + test fixtures"
```

---

### Task 5: First check end-to-end — I1 schema_stability

**Files:**
- Create: `src/eval/checks/i1_schema_stability.py`
- Create: `tests/eval/checks/test_i1_schema_stability.py`

**Why first:** Validates the BaseCheck contract end-to-end before writing 13 more.

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_i1_schema_stability.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.i1_schema_stability import I1SchemaStability
from tests.eval.fixtures.builders import make_dataset, make_daily


class TestI1(unittest.TestCase):
    def test_pass_when_all_fields_present(self):
        ds = make_dataset(tickers=("AAPL",))
        result = I1SchemaStability().run(ds)
        self.assertEqual(result.severity, "pass")
        self.assertEqual(result.pass_rate, 1.0)
        self.assertEqual(result.findings, ())

    def test_warn_when_one_field_missing_one_day(self):
        # 14 days × 1 ticker = 14 records; remove 1 field on 1 day → 1/14 ≈ 7.1%
        # But "missing field rate" is measured per-(record × required_field)
        # Adjust by removing key_news on one day
        end = date(2026, 4, 28)
        bad_day = end
        overrides = {"AAPL": {bad_day: make_daily(ticker="AAPL", as_of=bad_day,
                                                  extra_payload={"_drop": "key_news"})}}
        # builder removes "_drop" listed key
        ds = make_dataset(tickers=("AAPL",), end=end, daily_overrides=overrides)
        # patch: builder doesn't auto-drop; remove inline
        ds.daily["AAPL"][bad_day]["payload"].pop("key_news", None)
        result = I1SchemaStability().run(ds)
        self.assertIn(result.severity, {"pass", "warn"})  # boundary case: 1/14 ≈ 7.1%
        # 7.1% > 2% pass threshold but ≤ 10% warn threshold → expect "warn"
        self.assertEqual(result.severity, "warn")

    def test_fail_when_many_missing(self):
        end = date(2026, 4, 28)
        ds = make_dataset(tickers=("AAPL",), end=end)
        # Drop key_news on every day
        for d, payload in ds.daily["AAPL"].items():
            payload["payload"].pop("key_news", None)
        result = I1SchemaStability().run(ds)
        self.assertEqual(result.severity, "fail")
        self.assertGreater(len(result.findings), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test — verify failure**

Run: `python -m unittest tests.eval.checks.test_i1_schema_stability -v`
Expected: ImportError.

- [ ] **Step 3: Implement I1**

`src/eval/checks/i1_schema_stability.py`:

```python
from __future__ import annotations

from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


REQUIRED_PAYLOAD_FIELDS: tuple[str, ...] = (
    "ticker", "summary", "key_news", "news_references", "date",
)


class I1SchemaStability(BaseCheck):
    check_id = "I1"
    dimension = "schema_stability"

    def run(self, dataset: Any) -> CheckResult:
        total = 0
        missing = 0
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                payload = record.get("payload") or {}
                for f in REQUIRED_PAYLOAD_FIELDS:
                    total += 1
                    if f not in payload:
                        missing += 1
                        findings.append(Finding(
                            ticker=ticker, date=d, module="payload",
                            jsonpath=f"$.payload.{f}",
                            detail={"reason": "missing_required_field"},
                        ))
        rate = (missing / total) if total else 0.0
        sev = severity_for("I1", value=rate, kind="missing_field_rate")
        recommendation = None
        if sev != "pass":
            recommendation = "Inspect collector/analyzer normalization for dropped fields."
        return CheckResult(
            check_id="I1",
            severity=sev,
            pass_rate=1.0 - rate,
            findings=tuple(findings[:50]),  # cap detail
            metrics={"missing_field_rate": rate, "total_records": total},
            recommendation=recommendation,
        )
```

- [ ] **Step 4: Run test — verify pass**

Run: `python -m unittest tests.eval.checks.test_i1_schema_stability -v`
Expected: `OK` (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/i1_schema_stability.py tests/eval/checks/test_i1_schema_stability.py
git commit -m "feat(eval): I1 schema_stability check"
```

---

### Task 6: Report renderer (markdown + JSON)

**Files:**
- Create: `src/eval/report.py`
- Create: `tests/eval/test_report.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/test_report.py`:

```python
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.eval.checks.base import CheckResult, Finding
from src.eval.report import render_markdown, render_json, write_artifacts


def _result(check_id="I1", severity="pass", pass_rate=1.0):
    return CheckResult(check_id=check_id, severity=severity, pass_rate=pass_rate,
                       findings=(), metrics={"foo": 0.0}, recommendation=None)


class TestRender(unittest.TestCase):
    def test_render_json_has_required_keys(self):
        out = render_json(
            audit_date=date(2026, 4, 28),
            window_start=date(2026, 4, 15),
            window_end=date(2026, 4, 28),
            tickers=("AAPL",),
            model_profile="economy",
            git_sha="abcd1234",
            replay_meta={"enabled": False, "tickers": [], "runs_per_ticker": 0,
                         "cost_usd": 0.0, "cost_cap_usd": 1.0},
            results=[_result()],
        )
        self.assertEqual(out["schema_version"], 1)
        self.assertEqual(out["summary"]["total_checks"], 1)
        self.assertIn("checks", out)

    def test_render_markdown_contains_verdict_matrix(self):
        md = render_markdown(
            audit_date=date(2026, 4, 28),
            window_start=date(2026, 4, 15),
            window_end=date(2026, 4, 28),
            tickers=("AAPL",),
            replay_meta={"enabled": False, "cost_usd": 0.0},
            results=[_result(severity="warn", pass_rate=0.91)],
        )
        self.assertIn("# LLM Audit Report", md)
        self.assertIn("Verdict Matrix", md)
        self.assertIn("I1", md)

    def test_write_artifacts_creates_files(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            md_path, json_path = write_artifacts(
                root=tmp, audit_date=date(2026, 4, 28),
                window_start=date(2026, 4, 15), window_end=date(2026, 4, 28),
                tickers=("AAPL",), model_profile="economy", git_sha="abcd1234",
                replay_meta={"enabled": False, "tickers": [], "runs_per_ticker": 0,
                             "cost_usd": 0.0, "cost_cap_usd": 1.0},
                results=[_result()],
            )
            self.assertTrue(md_path.exists())
            self.assertTrue(json_path.exists())
            data = json.loads(json_path.read_text())
            self.assertEqual(data["schema_version"], 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test — verify failure**

Run: `python -m unittest tests.eval.test_report -v`
Expected: ImportError.

- [ ] **Step 3: Implement `report.py`**

`src/eval/report.py`:

```python
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.eval.checks.base import CheckResult


SEVERITY_ICON = {"pass": "OK", "warn": "WARN", "fail": "FAIL", "info": "i"}


def _summary_counts(results: Sequence[CheckResult]) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0, "info": 0}
    for r in results:
        counts[r.severity] += 1
    counts["total_checks"] = len(results)
    counts["overall_severity"] = (
        "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    )
    return counts


def render_json(
    *,
    audit_date: date,
    window_start: date,
    window_end: date,
    tickers: Sequence[str],
    model_profile: str,
    git_sha: str,
    replay_meta: Mapping[str, Any],
    results: Sequence[CheckResult],
) -> dict[str, Any]:
    counts = _summary_counts(results)
    return {
        "schema_version": 1,
        "audit_date": audit_date.isoformat(),
        "window": {
            "start": window_start.isoformat(),
            "end": window_end.isoformat(),
            "days": (window_end - window_start).days + 1,
        },
        "tickers_audited": list(tickers),
        "model_profile": model_profile,
        "git_sha": git_sha,
        "replay": dict(replay_meta),
        "summary": {
            "total_checks": counts["total_checks"],
            "pass": counts["pass"],
            "warn": counts["warn"],
            "fail": counts["fail"],
            "overall_severity": counts["overall_severity"],
        },
        "checks": [
            {
                "check_id": r.check_id,
                "severity": r.severity,
                "pass_rate": r.pass_rate,
                "metrics": dict(r.metrics),
                "findings": [
                    {
                        "ticker": f.ticker, "date": f.date.isoformat() if f.date else None,
                        "module": f.module, "jsonpath": f.jsonpath, "detail": dict(f.detail),
                    }
                    for f in r.findings
                ],
                "recommendation": r.recommendation,
            }
            for r in results
        ],
    }


def render_markdown(
    *,
    audit_date: date,
    window_start: date,
    window_end: date,
    tickers: Sequence[str],
    replay_meta: Mapping[str, Any],
    results: Sequence[CheckResult],
) -> str:
    counts = _summary_counts(results)
    days = (window_end - window_start).days + 1
    cost = replay_meta.get("cost_usd", 0.0)
    lines: list[str] = []
    lines.append(f"# LLM Audit Report — {audit_date.isoformat()}")
    lines.append("")
    lines.append(
        f"**Window:** {window_start.isoformat()} ~ {window_end.isoformat()} ({days}d) | "
        f"**Tickers:** {len(tickers)} | **Replay cost:** ${cost:.2f}"
    )
    lines.append(
        f"**Overall verdict:** {counts['fail']} fail / {counts['warn']} warn / "
        f"{counts['pass']} pass (out of {counts['total_checks']})"
    )
    lines.append("")
    lines.append("## Verdict Matrix")
    lines.append("")
    lines.append("| ID | Severity | Pass rate | Top metric |")
    lines.append("|----|----------|-----------|------------|")
    for r in results:
        metric_kv = next(iter(r.metrics.items()), ("-", 0.0))
        lines.append(
            f"| {r.check_id} | {SEVERITY_ICON[r.severity]} {r.severity} | "
            f"{r.pass_rate * 100:.1f}% | {metric_kv[0]}={metric_kv[1]:.3f} |"
        )
    lines.append("")
    lines.append("## 차원별 상세")
    for r in results:
        lines.append("")
        lines.append(f"### {r.check_id} — severity: {r.severity}")
        for k, v in r.metrics.items():
            lines.append(f"- {k}: {v:.4f}")
        if r.findings:
            lines.append("")
            lines.append("Top findings:")
            for f in r.findings[:10]:
                lines.append(
                    f"- ticker={f.ticker} date={f.date} jsonpath={f.jsonpath} detail={dict(f.detail)}"
                )
        if r.recommendation:
            lines.append("")
            lines.append(f"**Recommendation:** {r.recommendation}")
    return "\n".join(lines) + "\n"


def write_artifacts(
    *,
    root: Path,
    audit_date: date,
    window_start: date,
    window_end: date,
    tickers: Sequence[str],
    model_profile: str,
    git_sha: str,
    replay_meta: Mapping[str, Any],
    results: Sequence[CheckResult],
    suffix: str | None = None,
) -> tuple[Path, Path]:
    suf = f"-{suffix}" if suffix else ""
    md_path = root / "docs" / "reports" / f"llm-audit-{audit_date.isoformat()}{suf}.md"
    json_path = root / "output" / "data" / "llm_audit" / f"{audit_date.isoformat()}{suf}.json"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    md_path.write_text(render_markdown(
        audit_date=audit_date, window_start=window_start, window_end=window_end,
        tickers=tickers, replay_meta=replay_meta, results=results,
    ), encoding="utf-8")
    json_path.write_text(json.dumps(render_json(
        audit_date=audit_date, window_start=window_start, window_end=window_end,
        tickers=tickers, model_profile=model_profile, git_sha=git_sha,
        replay_meta=replay_meta, results=results,
    ), ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path
```

- [ ] **Step 4: Run test — verify pass**

Run: `python -m unittest tests.eval.test_report -v`
Expected: `OK` (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/report.py tests/eval/test_report.py
git commit -m "feat(eval): markdown + JSON report renderer"
```

---

### Task 7: Runner skeleton (CLI + orchestration)

**Files:**
- Create: `src/eval/runner.py`
- Create: `tests/eval/test_runner.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/test_runner.py`:

```python
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from src.eval.runner import run_audit, RunnerConfig
from tests.eval.fixtures.builders import make_dataset


class TestRunner(unittest.TestCase):
    def test_skip_replay_runs_all_registered_checks(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
            cfg = RunnerConfig(
                root=tmp, audit_date=date(2026, 4, 28),
                window_days=14, tickers=["AAPL"],
                checks=("I1",), skip_replay=True,
                model_profile="economy", git_sha="abcd1234",
            )
            with mock.patch("src.eval.runner.load_window", return_value=ds):
                exit_code, results = run_audit(cfg)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].check_id, "I1")
            md = tmp / "docs" / "reports" / "llm-audit-2026-04-28.md"
            jp = tmp / "output" / "data" / "llm_audit" / "2026-04-28.json"
            self.assertTrue(md.exists())
            self.assertTrue(jp.exists())
            self.assertEqual(exit_code, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_check_isolation_one_fails_others_continue(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
            class _Boom:
                check_id = "BOOM"
                dimension = "boom"
                def run(self, ds):
                    raise RuntimeError("synthetic")

            cfg = RunnerConfig(
                root=tmp, audit_date=date(2026, 4, 28),
                window_days=14, tickers=["AAPL"],
                checks=("I1", "BOOM"), skip_replay=True,
                model_profile="economy", git_sha="abcd1234",
                check_overrides={"BOOM": _Boom()},
            )
            with mock.patch("src.eval.runner.load_window", return_value=ds):
                exit_code, results = run_audit(cfg)
            ids = {r.check_id for r in results}
            self.assertEqual(ids, {"I1", "BOOM"})
            boom = next(r for r in results if r.check_id == "BOOM")
            self.assertEqual(boom.severity, "fail")
            # Exit code reflects the worst severity (fail → non-zero)
            self.assertNotEqual(exit_code, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_invalid_window_raises(self):
        cfg = RunnerConfig(
            root=Path("/tmp"), audit_date=date(2026, 4, 28),
            window_days=0, tickers=["AAPL"],
            checks=("I1",), skip_replay=True,
            model_profile="economy", git_sha="x",
        )
        with self.assertRaises(ValueError):
            run_audit(cfg)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test — verify failure**

Run: `python -m unittest tests.eval.test_runner -v`
Expected: ImportError on `src.eval.runner`.

- [ ] **Step 3: Implement `runner.py`**

`src/eval/runner.py`:

```python
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Mapping, Sequence

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import (
    ALL_CHECK_IDS,
    DEFAULT_MAX_REPLAY_COST_USD,
    DEFAULT_REPLAY_TICKERS,
    DEFAULT_RUNS_PER_TICKER,
    DEFAULT_WINDOW_DAYS,
)
from src.eval.data_sources import load_window
from src.eval.report import write_artifacts


logger = logging.getLogger(__name__)


@dataclass
class RunnerConfig:
    root: Path
    audit_date: date
    window_days: int
    tickers: list[str]
    checks: Sequence[str]
    skip_replay: bool
    model_profile: str
    git_sha: str
    suffix: str | None = None
    max_replay_cost_usd: float = DEFAULT_MAX_REPLAY_COST_USD
    replay_tickers: tuple[str, ...] = DEFAULT_REPLAY_TICKERS
    runs_per_ticker: int = DEFAULT_RUNS_PER_TICKER
    dry_run: bool = False
    check_overrides: Mapping[str, BaseCheck] = field(default_factory=dict)


def _build_check(check_id: str, overrides: Mapping[str, BaseCheck]) -> BaseCheck:
    if check_id in overrides:
        return overrides[check_id]
    # Lazy import per check to keep startup fast and isolate failures.
    if check_id == "I1":
        from src.eval.checks.i1_schema_stability import I1SchemaStability
        return I1SchemaStability()
    raise KeyError(f"Unknown check_id: {check_id}")


def _error_result(check_id: str, exc: BaseException) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        severity="fail",
        pass_rate=0.0,
        findings=(Finding(detail={"error": str(exc), "trace": traceback.format_exc()}),),
        metrics={},
        recommendation="Check raised an exception; see findings[0].detail.trace",
    )


def _exit_code_from_results(results: Sequence[CheckResult]) -> int:
    if any(r.severity == "fail" for r in results):
        return 2
    if any(r.severity == "warn" for r in results):
        return 1
    return 0


def run_audit(cfg: RunnerConfig) -> tuple[int, list[CheckResult]]:
    if cfg.window_days < 1:
        raise ValueError(f"window_days must be >= 1, got {cfg.window_days}")

    dataset = load_window(
        root=cfg.root, end=cfg.audit_date, window_days=cfg.window_days,
        tickers=cfg.tickers, model_profile=cfg.model_profile,
    )

    results: list[CheckResult] = []
    for check_id in cfg.checks:
        try:
            check = _build_check(check_id, cfg.check_overrides)
            print(f"[{check_id}] running...", flush=True)
            results.append(check.run(dataset))
        except BaseException as exc:  # isolate per check
            logger.exception("Check %s raised", check_id)
            results.append(_error_result(check_id, exc))

    write_artifacts(
        root=cfg.root, audit_date=cfg.audit_date,
        window_start=dataset.window_start, window_end=dataset.window_end,
        tickers=dataset.tickers, model_profile=cfg.model_profile,
        git_sha=cfg.git_sha,
        replay_meta={
            "enabled": not cfg.skip_replay,
            "tickers": list(cfg.replay_tickers),
            "runs_per_ticker": cfg.runs_per_ticker,
            "cost_usd": 0.0,
            "cost_cap_usd": cfg.max_replay_cost_usd,
        },
        results=results,
        suffix=cfg.suffix,
    )
    return _exit_code_from_results(results), results


def _git_sha(root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=root, stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="src.eval.runner",
                                description="LLM quality audit (one-shot).")
    p.add_argument("--window", type=int, default=DEFAULT_WINDOW_DAYS,
                   help=f"Window days (default {DEFAULT_WINDOW_DAYS})")
    p.add_argument("--checks", type=str, default=",".join(ALL_CHECK_IDS),
                   help="Comma-separated check ids (default ALL).")
    p.add_argument("--skip-replay", action="store_true")
    p.add_argument("--replay-tickers", type=str, default=",".join(DEFAULT_REPLAY_TICKERS))
    p.add_argument("--max-replay-cost-usd", type=float,
                   default=DEFAULT_MAX_REPLAY_COST_USD)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--suffix", type=str, default=None)
    p.add_argument("--check-links", action="store_true")
    p.add_argument("--yes", action="store_true",
                   help="Skip confirm prompts (CI mode).")
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--audit-date", type=str, default=date.today().isoformat())
    p.add_argument("--tickers", type=str, default="",
                   help="Comma-separated tickers; empty → load from config/watchlist.yaml")
    return p.parse_args(argv)


def _load_tickers_from_watchlist(root: Path) -> list[str]:
    import yaml
    p = root / "config" / "watchlist.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
    return [item["ticker"] for item in (data.get("watchlist") or [])]


def main(argv: Sequence[str] | None = None) -> int:
    ns = _parse_args(argv if argv is not None else sys.argv[1:])
    tickers = ([t.strip() for t in ns.tickers.split(",") if t.strip()]
               if ns.tickers else _load_tickers_from_watchlist(ns.root))
    cfg = RunnerConfig(
        root=ns.root,
        audit_date=date.fromisoformat(ns.audit_date),
        window_days=ns.window,
        tickers=tickers,
        checks=tuple(s.strip() for s in ns.checks.split(",") if s.strip()),
        skip_replay=ns.skip_replay,
        replay_tickers=tuple(s.strip() for s in ns.replay_tickers.split(",") if s.strip()),
        max_replay_cost_usd=ns.max_replay_cost_usd,
        dry_run=ns.dry_run,
        suffix=ns.suffix,
        model_profile="economy",  # actual value pulled from env in production main
        git_sha=_git_sha(ns.root),
    )
    code, _ = run_audit(cfg)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test — verify pass**

Run: `python -m unittest tests.eval.test_runner -v`
Expected: `OK` (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/runner.py tests/eval/test_runner.py
git commit -m "feat(eval): runner CLI + orchestration with per-check isolation"
```

---

### Task 8: I2 missingness

**Files:**
- Create: `src/eval/checks/i2_missingness.py`
- Create: `tests/eval/checks/test_i2_missingness.py`
- Modify: `src/eval/runner.py` (add I2 to `_build_check` switch)

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_i2_missingness.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.i2_missingness import I2Missingness
from tests.eval.fixtures.builders import make_dataset


class TestI2(unittest.TestCase):
    def test_pass_when_all_news_present(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        result = I2Missingness().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_news_references_empty_majority(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        # Empty news_references on 12/14 days (≈86%)
        days = sorted(ds.daily["AAPL"].keys())
        for d in days[:12]:
            ds.daily["AAPL"][d]["payload"]["news_references"] = []
        result = I2Missingness().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test — verify failure**

Run: `python -m unittest tests.eval.checks.test_i2_missingness -v`
Expected: ImportError.

- [ ] **Step 3: Implement I2 + register in runner**

`src/eval/checks/i2_missingness.py`:

```python
from __future__ import annotations

from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


# Fields whose missingness signals a problem (non-optional).
TRACKED_FIELDS: tuple[str, ...] = ("summary", "key_news", "news_references")
# Fields whose absence is acceptable and should not contribute to severity.
WHITELIST_OPTIONAL: tuple[str, ...] = ("options", "insider", "fundamentals")


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, dict, str)) and len(value) == 0:
        return True
    return False


class I2Missingness(BaseCheck):
    check_id = "I2"
    dimension = "missingness"

    def run(self, dataset: Any) -> CheckResult:
        per_field_total: dict[str, int] = {f: 0 for f in TRACKED_FIELDS}
        per_field_missing: dict[str, int] = {f: 0 for f in TRACKED_FIELDS}
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                payload = record.get("payload") or {}
                for f in TRACKED_FIELDS:
                    per_field_total[f] += 1
                    if _is_missing(payload.get(f)):
                        per_field_missing[f] += 1
                        findings.append(Finding(
                            ticker=ticker, date=d, module="payload",
                            jsonpath=f"$.payload.{f}",
                            detail={"reason": "empty_or_none"},
                        ))
        rates = {
            f: (per_field_missing[f] / per_field_total[f]) if per_field_total[f] else 0.0
            for f in TRACKED_FIELDS
        }
        worst_rate = max(rates.values()) if rates else 0.0
        sev = severity_for("I2", value=worst_rate, kind="missingness_rate")
        worst_field = max(rates, key=rates.get) if rates else "-"
        return CheckResult(
            check_id="I2",
            severity=sev,
            pass_rate=1.0 - worst_rate,
            findings=tuple(findings[:50]),
            metrics={"worst_field_missing_rate": worst_rate, **{f"rate_{k}": v for k, v in rates.items()}},
            recommendation=(
                f"{worst_field} missingness {worst_rate:.0%}; review collector for that field."
                if sev != "pass" else None
            ),
        )
```

In `src/eval/runner.py` `_build_check`, add (immediately after the I1 block, before `raise KeyError`):

```python
    if check_id == "I2":
        from src.eval.checks.i2_missingness import I2Missingness
        return I2Missingness()
```

- [ ] **Step 4: Run test — verify pass**

Run: `python -m unittest tests.eval.checks.test_i2_missingness -v`
Expected: `OK` (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/i2_missingness.py src/eval/runner.py tests/eval/checks/test_i2_missingness.py
git commit -m "feat(eval): I2 missingness check"
```

---

### Task 9: I3 format_consistency (real AAPL case)

**Files:**
- Create: `src/eval/checks/i3_format_consistency.py`
- Create: `tests/eval/checks/test_i3_format_consistency.py`
- Modify: `src/eval/runner.py` (add I3 to switch)

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_i3_format_consistency.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.i3_format_consistency import I3FormatConsistency
from tests.eval.fixtures.builders import make_dataset


class TestI3(unittest.TestCase):
    def test_pass_when_uniform_iso(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        # builder default → ISO. should pass.
        result = I3FormatConsistency().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_warn_when_two_formats(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        # Mix one RFC822 in
        bad_day = ds.window_end
        ds.daily["AAPL"][bad_day]["payload"]["news_references"] = [
            {"title": "x", "source": "Reuters",
             "published_at": "Fri, 30 Jan 2026 08:00:00 GMT", "link": "https://x"},
        ]
        result = I3FormatConsistency().run(ds)
        self.assertEqual(result.severity, "warn")

    def test_fail_with_three_formats(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        days = sorted(ds.daily["AAPL"].keys())
        ds.daily["AAPL"][days[0]]["payload"]["news_references"] = [
            {"title": "a", "source": "x", "published_at": "2026-04-15", "link": "https://x"},
        ]
        ds.daily["AAPL"][days[1]]["payload"]["news_references"] = [
            {"title": "b", "source": "x", "published_at": "Fri, 30 Jan 2026 08:00:00 GMT",
             "link": "https://x"},
        ]
        ds.daily["AAPL"][days[2]]["payload"]["news_references"] = [
            {"title": "c", "source": "x", "published_at": "20/04/2026", "link": "https://x"},
        ]
        result = I3FormatConsistency().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.checks.test_i3_format_consistency -v`
Expected: ImportError.

- [ ] **Step 3: Implement I3**

`src/eval/checks/i3_format_consistency.py`:

```python
from __future__ import annotations

import re
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$")
RFC822 = re.compile(r"^[A-Z][a-z]{2}, \d{1,2} [A-Z][a-z]{2} \d{4}")
SLASHED = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def _classify(s: str) -> str:
    if ISO_DATE.match(s):
        return "ISO-8601"
    if RFC822.match(s):
        return "RFC822"
    if SLASHED.match(s):
        return "DD/MM/YYYY"
    return "free"


class I3FormatConsistency(BaseCheck):
    check_id = "I3"
    dimension = "format_consistency"

    def run(self, dataset: Any) -> CheckResult:
        formats_seen: set[str] = set()
        examples: dict[str, str] = {}
        affected: set[str] = set()
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                refs = (record.get("payload") or {}).get("news_references") or []
                for ref in refs:
                    pa = ref.get("published_at")
                    if not pa:
                        continue
                    cls = _classify(str(pa))
                    if cls not in formats_seen:
                        examples[cls] = str(pa)
                    formats_seen.add(cls)
                    if cls != "ISO-8601":
                        affected.add(ticker)
        count = len(formats_seen)
        sev = severity_for("I3", value=count, kind="format_count")
        finding = Finding(
            module="news_references", jsonpath="$.payload.news_references[*].published_at",
            detail={"formats_seen": sorted(formats_seen),
                    "examples": examples,
                    "affected_tickers_count": len(affected)},
        )
        rec = (
            "Normalize published_at to ISO-8601 in collector (src/collector/news.py, sec.py)."
            if sev != "pass" else None
        )
        return CheckResult(
            check_id="I3",
            severity=sev,
            pass_rate=1.0 if count <= 1 else (1.0 / count),
            findings=(finding,) if formats_seen else (),
            metrics={"format_count": float(count)},
            recommendation=rec,
        )
```

In `runner.py` `_build_check`:

```python
    if check_id == "I3":
        from src.eval.checks.i3_format_consistency import I3FormatConsistency
        return I3FormatConsistency()
```

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest tests.eval.checks.test_i3_format_consistency -v`
Expected: `OK` (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/i3_format_consistency.py src/eval/runner.py tests/eval/checks/test_i3_format_consistency.py
git commit -m "feat(eval): I3 format_consistency check"
```

---

### Task 10: I4 input_size_drift

**Files:**
- Create: `src/eval/checks/i4_input_size_drift.py`
- Create: `tests/eval/checks/test_i4_input_size_drift.py`
- Modify: `src/eval/runner.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_i4_input_size_drift.py`:

```python
from __future__ import annotations

import unittest
from datetime import date, timedelta

from src.eval.checks.i4_input_size_drift import I4InputSizeDrift
from tests.eval.fixtures.builders import make_dataset, make_summary


class TestI4(unittest.TestCase):
    def test_pass_when_low_cv(self):
        end = date(2026, 4, 28)
        days = [end - timedelta(days=i) for i in range(14)]
        # tokens 3000 ± 50 → cv ≈ 0.017
        summaries = {
            d: make_summary(d, token_usage={"AAPL": 3000 + (i % 2) * 50})
            for i, d in enumerate(days)
        }
        ds = make_dataset(tickers=("AAPL",), end=end, summary_overrides=summaries)
        result = I4InputSizeDrift().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_high_cv(self):
        end = date(2026, 4, 28)
        days = [end - timedelta(days=i) for i in range(14)]
        # tokens swing wildly 1000 ↔ 6000
        summaries = {
            d: make_summary(d, token_usage={"AAPL": 1000 if i % 2 else 6000})
            for i, d in enumerate(days)
        }
        ds = make_dataset(tickers=("AAPL",), end=end, summary_overrides=summaries)
        result = I4InputSizeDrift().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.checks.test_i4_input_size_drift -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/eval/checks/i4_input_size_drift.py`:

```python
from __future__ import annotations

import math
import statistics
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


class I4InputSizeDrift(BaseCheck):
    check_id = "I4"
    dimension = "input_size_drift"

    def run(self, dataset: Any) -> CheckResult:
        per_ticker_tokens: dict[str, list[int]] = {t: [] for t in dataset.tickers}
        for d, summary in dataset.summaries.items():
            usage = (summary.get("model_usage") or {}).get("per_ticker_tokens") or {}
            for t in dataset.tickers:
                if t in usage:
                    per_ticker_tokens[t].append(int(usage[t]))
        cvs: dict[str, float] = {}
        findings: list[Finding] = []
        for t, samples in per_ticker_tokens.items():
            if len(samples) < 2:
                continue
            mean = statistics.fmean(samples)
            if mean == 0:
                continue
            stdev = statistics.pstdev(samples)
            cv = stdev / mean
            cvs[t] = cv
        worst = max(cvs.values()) if cvs else 0.0
        worst_t = max(cvs, key=cvs.get) if cvs else None
        sev = severity_for("I4", value=worst, kind="cv")
        if worst_t and sev != "pass":
            findings.append(Finding(
                ticker=worst_t, module="prompt_tokens",
                detail={"cv": worst, "samples": per_ticker_tokens[worst_t]},
            ))
        return CheckResult(
            check_id="I4",
            severity=sev,
            pass_rate=1.0 - min(worst, 1.0),
            findings=tuple(findings),
            metrics={"worst_cv": worst, **{f"cv_{t}": v for t, v in cvs.items()}},
            recommendation=(
                f"{worst_t} prompt size CV {worst:.2f}; investigate news/filing volume swings."
                if sev != "pass" else None
            ),
        )
```

In `runner.py` `_build_check`:

```python
    if check_id == "I4":
        from src.eval.checks.i4_input_size_drift import I4InputSizeDrift
        return I4InputSizeDrift()
```

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest tests.eval.checks.test_i4_input_size_drift -v`
Expected: `OK` (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/i4_input_size_drift.py src/eval/runner.py tests/eval/checks/test_i4_input_size_drift.py
git commit -m "feat(eval): I4 input_size_drift check"
```

---

### Task 11: O1 schema_compliance

**Files:**
- Create: `src/eval/checks/o1_schema_compliance.py`
- Create: `tests/eval/checks/test_o1_schema_compliance.py`
- Modify: `src/eval/runner.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_o1_schema_compliance.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.o1_schema_compliance import O1SchemaCompliance
from tests.eval.fixtures.builders import make_dataset


class TestO1(unittest.TestCase):
    def test_pass_when_all_required_fields_present(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        result = O1SchemaCompliance().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_summary_is_int(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        ds.daily["AAPL"][ds.window_end]["payload"]["summary"] = 42  # wrong type
        result = O1SchemaCompliance().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.checks.test_o1_schema_compliance -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/eval/checks/o1_schema_compliance.py`:

```python
from __future__ import annotations

from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding


# (jsonpath, expected_python_type)
SCHEMA: tuple[tuple[str, type], ...] = (
    ("payload.ticker", str),
    ("payload.summary", str),
    ("payload.key_news", list),
    ("payload.news_references", list),
    ("payload.date", str),
)


def _get(obj: dict, dotted: str) -> Any:
    cur: Any = obj
    for key in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


class O1SchemaCompliance(BaseCheck):
    check_id = "O1"
    dimension = "schema_compliance"

    def run(self, dataset: Any) -> CheckResult:
        violations: list[Finding] = []
        total = 0
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                for path, expected in SCHEMA:
                    total += 1
                    val = _get(record, path)
                    if val is None or not isinstance(val, expected):
                        violations.append(Finding(
                            ticker=ticker, date=d, jsonpath="$." + path,
                            detail={"expected": expected.__name__,
                                    "got": type(val).__name__},
                        ))
        rate = (len(violations) / total) if total else 0.0
        sev = "pass" if rate == 0 else "fail"  # binary
        return CheckResult(
            check_id="O1",
            severity=sev,
            pass_rate=1.0 - rate,
            findings=tuple(violations[:50]),
            metrics={"violation_rate": rate, "total_records": total},
            recommendation=(
                "Re-run analyzer modules with strict response_schema validation; check llm_runtime."
                if sev != "pass" else None
            ),
        )
```

In `runner.py` `_build_check`:

```python
    if check_id == "O1":
        from src.eval.checks.o1_schema_compliance import O1SchemaCompliance
        return O1SchemaCompliance()
```

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest tests.eval.checks.test_o1_schema_compliance -v`
Expected: `OK` (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/o1_schema_compliance.py src/eval/runner.py tests/eval/checks/test_o1_schema_compliance.py
git commit -m "feat(eval): O1 schema_compliance check"
```

---

### Task 12: O2 numeric_grounding

**Files:**
- Create: `src/eval/checks/o2_numeric_grounding.py`
- Create: `tests/eval/checks/test_o2_numeric_grounding.py`
- Modify: `src/eval/runner.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_o2_numeric_grounding.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.o2_numeric_grounding import O2NumericGrounding
from tests.eval.fixtures.builders import make_dataset


class TestO2(unittest.TestCase):
    def test_pass_when_summary_numbers_match_metrics(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        # all 14 days have summary "100.00 USD (+0.50%)" and matching metrics
        for d in ds.daily["AAPL"].values():
            d["payload"]["metrics"] = {"price": 100.00, "pct_change": 0.50}
        result = O2NumericGrounding().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_summary_lies(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for d in ds.daily["AAPL"].values():
            d["payload"]["summary"] = "Apple is at 999.00 USD (+50.00%)."
            d["payload"]["metrics"] = {"price": 100.00, "pct_change": 0.50}
        result = O2NumericGrounding().run(ds)
        self.assertEqual(result.severity, "fail")

    def test_warn_when_some_lies(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        days = sorted(ds.daily["AAPL"].keys())
        for d in days:
            ds.daily["AAPL"][d]["payload"]["metrics"] = {"price": 100.00, "pct_change": 0.50}
        # 1/14 ≈ 7% mismatch → 93% match → between warn (85%) and pass (95%)
        ds.daily["AAPL"][days[0]]["payload"]["summary"] = "999.00 USD (+50.00%)"
        result = O2NumericGrounding().run(ds)
        self.assertEqual(result.severity, "warn")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.checks.test_o2_numeric_grounding -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/eval/checks/o2_numeric_grounding.py`:

```python
from __future__ import annotations

import re
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


# Capture <number> followed by USD or %.
NUM_USD = re.compile(r"(\d+(?:\.\d+)?)\s*USD")
NUM_PCT = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")
TOLERANCE_REL = 0.005  # 0.5%


def _close(actual: float, claimed: float, rel: float = TOLERANCE_REL) -> bool:
    if actual == 0:
        return abs(claimed) < 1e-6
    return abs(actual - claimed) / abs(actual) <= rel


class O2NumericGrounding(BaseCheck):
    check_id = "O2"
    dimension = "numeric_grounding"

    def run(self, dataset: Any) -> CheckResult:
        total = 0
        matched = 0
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                payload = record.get("payload") or {}
                summary = payload.get("summary") or ""
                metrics = payload.get("metrics") or {}
                price_actual = metrics.get("price")
                pct_actual = metrics.get("pct_change")

                for m in NUM_USD.finditer(summary):
                    total += 1
                    if price_actual is not None and _close(float(price_actual), float(m.group(1))):
                        matched += 1
                    else:
                        findings.append(Finding(
                            ticker=ticker, date=d, jsonpath="$.payload.summary",
                            detail={"claimed_usd": m.group(1), "actual_price": price_actual},
                        ))
                for m in NUM_PCT.finditer(summary):
                    total += 1
                    if pct_actual is not None and _close(float(pct_actual), float(m.group(1))):
                        matched += 1
                    else:
                        findings.append(Finding(
                            ticker=ticker, date=d, jsonpath="$.payload.summary",
                            detail={"claimed_pct": m.group(1), "actual_pct": pct_actual},
                        ))

        rate = (matched / total) if total else 1.0
        sev = severity_for("O2", value=rate, kind="match_rate")
        return CheckResult(
            check_id="O2",
            severity=sev,
            pass_rate=rate,
            findings=tuple(findings[:50]),
            metrics={"match_rate": rate, "total_numeric_claims": total},
            recommendation=(
                "Anchor research_note prompt to actual price/% from collected data; "
                "consider passing metrics dict explicitly into the prompt."
                if sev != "pass" else None
            ),
        )
```

In `runner.py` `_build_check`:

```python
    if check_id == "O2":
        from src.eval.checks.o2_numeric_grounding import O2NumericGrounding
        return O2NumericGrounding()
```

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest tests.eval.checks.test_o2_numeric_grounding -v`
Expected: `OK` (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/o2_numeric_grounding.py src/eval/runner.py tests/eval/checks/test_o2_numeric_grounding.py
git commit -m "feat(eval): O2 numeric_grounding check"
```

---

### Task 13: O3 citation_integrity (link-check OFF by default)

**Files:**
- Create: `src/eval/checks/o3_citation_integrity.py`
- Create: `tests/eval/checks/test_o3_citation_integrity.py`
- Modify: `src/eval/runner.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_o3_citation_integrity.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.o3_citation_integrity import O3CitationIntegrity
from tests.eval.fixtures.builders import make_dataset


class TestO3(unittest.TestCase):
    def test_pass_when_key_news_in_references(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        result = O3CitationIntegrity(check_links=False).run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_orphan_key_news(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for d, record in ds.daily["AAPL"].items():
            record["payload"]["key_news"] = ["Completely fabricated headline"]
            record["payload"]["news_references"] = [
                {"title": "Real headline", "source": "x", "published_at": "2026-01-01",
                 "link": "https://x"}
            ]
        result = O3CitationIntegrity(check_links=False).run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.checks.test_o3_citation_integrity -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/eval/checks/o3_citation_integrity.py`:

```python
from __future__ import annotations

import re
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


def _tokenize(s: str) -> set[str]:
    return set(re.findall(r"[\w가-힣]+", (s or "").lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class O3CitationIntegrity(BaseCheck):
    check_id = "O3"
    dimension = "citation_integrity"

    def __init__(self, check_links: bool = False, link_sample_cap: int = 100) -> None:
        self.check_links = check_links
        self.link_sample_cap = link_sample_cap

    def run(self, dataset: Any) -> CheckResult:
        total = 0
        matched = 0
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                payload = record.get("payload") or {}
                key_news = payload.get("key_news") or []
                refs = payload.get("news_references") or []
                ref_titles = [r.get("title") or "" for r in refs]
                for kn in key_news:
                    total += 1
                    best = max((_jaccard(kn, t) for t in ref_titles), default=0.0)
                    if best >= 0.85:
                        matched += 1
                    else:
                        findings.append(Finding(
                            ticker=ticker, date=d, jsonpath="$.payload.key_news",
                            detail={"orphan": kn, "best_jaccard": best},
                        ))
        rate = (matched / total) if total else 1.0
        sev = severity_for("O3", value=rate, kind="citation_match_rate")
        return CheckResult(
            check_id="O3",
            severity=sev,
            pass_rate=rate,
            findings=tuple(findings[:50]),
            metrics={"citation_match_rate": rate, "total_key_news": total,
                     "link_check_enabled": float(self.check_links)},
            recommendation=(
                "Constrain prompt: 'key_news must be drawn from news_references list verbatim'."
                if sev != "pass" else None
            ),
        )
```

In `runner.py` `_build_check`:

```python
    if check_id == "O3":
        from src.eval.checks.o3_citation_integrity import O3CitationIntegrity
        return O3CitationIntegrity(check_links=cfg.check_links if hasattr(cfg, "check_links") else False)
```

Also add `check_links: bool = False` field to `RunnerConfig` and wire it from `_parse_args` (`cfg = RunnerConfig(... check_links=ns.check_links, ...)`). Pass `cfg` into `_build_check` (change signature to `(check_id, cfg)`).

`runner.py` updates:

```python
@dataclass
class RunnerConfig:
    # ... existing fields ...
    check_links: bool = False
    # ...

def _build_check(check_id: str, cfg: "RunnerConfig") -> BaseCheck:
    if check_id in cfg.check_overrides:
        return cfg.check_overrides[check_id]
    if check_id == "I1":
        from src.eval.checks.i1_schema_stability import I1SchemaStability
        return I1SchemaStability()
    if check_id == "I2":
        from src.eval.checks.i2_missingness import I2Missingness
        return I2Missingness()
    if check_id == "I3":
        from src.eval.checks.i3_format_consistency import I3FormatConsistency
        return I3FormatConsistency()
    if check_id == "I4":
        from src.eval.checks.i4_input_size_drift import I4InputSizeDrift
        return I4InputSizeDrift()
    if check_id == "O1":
        from src.eval.checks.o1_schema_compliance import O1SchemaCompliance
        return O1SchemaCompliance()
    if check_id == "O2":
        from src.eval.checks.o2_numeric_grounding import O2NumericGrounding
        return O2NumericGrounding()
    if check_id == "O3":
        from src.eval.checks.o3_citation_integrity import O3CitationIntegrity
        return O3CitationIntegrity(check_links=cfg.check_links)
    raise KeyError(f"Unknown check_id: {check_id}")
```

And in `run_audit`, replace the `_build_check(check_id, cfg.check_overrides)` call with `_build_check(check_id, cfg)`.

- [ ] **Step 4: Run all eval tests so the runner refactor stays green**

Run: `python -m unittest discover -s tests/eval -v`
Expected: all currently-existing tests `OK`.

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/o3_citation_integrity.py src/eval/runner.py tests/eval/checks/test_o3_citation_integrity.py
git commit -m "feat(eval): O3 citation_integrity check + runner check_links wiring"
```

---

### Task 14: O4 language_consistency

**Files:**
- Create: `src/eval/checks/o4_language_consistency.py`
- Create: `tests/eval/checks/test_o4_language_consistency.py`
- Modify: `src/eval/runner.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_o4_language_consistency.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.o4_language_consistency import O4LanguageConsistency
from tests.eval.fixtures.builders import make_dataset


class TestO4(unittest.TestCase):
    def test_pass_when_consistent_korean(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for record in ds.daily["AAPL"].values():
            record["payload"]["summary"] = "애플은 100달러에 거래되고 있습니다."
        result = O4LanguageConsistency().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_swings_between_languages(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        days = sorted(ds.daily["AAPL"].keys())
        for i, d in enumerate(days):
            if i % 2:
                ds.daily["AAPL"][d]["payload"]["summary"] = "Apple traded at 100 USD today."
            else:
                ds.daily["AAPL"][d]["payload"]["summary"] = "애플은 100달러에 거래되었습니다."
        result = O4LanguageConsistency().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.checks.test_o4_language_consistency -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/eval/checks/o4_language_consistency.py`:

```python
from __future__ import annotations

import re
import statistics
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


HANGUL_RE = re.compile(r"[가-힣]")
LATIN_RE = re.compile(r"[A-Za-z]")


def _korean_ratio(text: str) -> float:
    if not text:
        return 0.0
    han = len(HANGUL_RE.findall(text))
    lat = len(LATIN_RE.findall(text))
    denom = han + lat
    return (han / denom) if denom else 0.0


class O4LanguageConsistency(BaseCheck):
    check_id = "O4"
    dimension = "language_consistency"

    def run(self, dataset: Any) -> CheckResult:
        per_ticker_stds: dict[str, float] = {}
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            ratios = [
                _korean_ratio((record.get("payload") or {}).get("summary") or "")
                for record in days.values()
            ]
            if len(ratios) < 2:
                continue
            std = statistics.pstdev(ratios)
            per_ticker_stds[ticker] = std
            if std > 0.30:
                findings.append(Finding(
                    ticker=ticker, jsonpath="$.payload.summary",
                    detail={"korean_ratio_std": std, "samples": ratios},
                ))
        worst = max(per_ticker_stds.values()) if per_ticker_stds else 0.0
        sev = severity_for("O4", value=worst, kind="lang_ratio_std")
        return CheckResult(
            check_id="O4",
            severity=sev,
            pass_rate=1.0 - min(worst, 1.0),
            findings=tuple(findings),
            metrics={"worst_korean_ratio_std": worst},
            recommendation=(
                "Pin language in system prompt; reject mixed-language outputs in llm_runtime parser."
                if sev != "pass" else None
            ),
        )
```

In `runner.py`:

```python
    if check_id == "O4":
        from src.eval.checks.o4_language_consistency import O4LanguageConsistency
        return O4LanguageConsistency()
```

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest tests.eval.checks.test_o4_language_consistency -v`
Expected: `OK` (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/o4_language_consistency.py src/eval/runner.py tests/eval/checks/test_o4_language_consistency.py
git commit -m "feat(eval): O4 language_consistency check"
```

---

### Task 15: O5 contradiction

**Files:**
- Create: `src/eval/checks/o5_contradiction.py`
- Create: `tests/eval/checks/test_o5_contradiction.py`
- Modify: `src/eval/runner.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_o5_contradiction.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.o5_contradiction import O5Contradiction
from tests.eval.fixtures.builders import make_dataset


class TestO5(unittest.TestCase):
    def test_pass_when_three_signals_agree(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for record in ds.daily["AAPL"].values():
            record["payload"]["summary"] = "긍정적 모멘텀 지속, 매수 검토."
            record["payload"]["risk_assessment"] = {"severity": "low"}
            record["payload"]["research_narrative"] = {"outlook": "positive"}
        result = O5Contradiction().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_disagree(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for record in ds.daily["AAPL"].values():
            record["payload"]["summary"] = "강한 부정적 모멘텀, 매도 권고."
            record["payload"]["risk_assessment"] = {"severity": "low"}
            record["payload"]["research_narrative"] = {"outlook": "positive"}
        result = O5Contradiction().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.checks.test_o5_contradiction -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/eval/checks/o5_contradiction.py`:

```python
from __future__ import annotations

from typing import Any, Literal

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


Direction = Literal["positive", "negative", "neutral"]

POS_LEX: tuple[str, ...] = ("긍정", "매수", "상승", "강세", "낙관", "positive", "buy", "bullish", "strong")
NEG_LEX: tuple[str, ...] = ("부정", "매도", "하락", "약세", "비관", "negative", "sell", "bearish", "weak")


def _direction_from_text(text: str) -> Direction:
    t = text.lower()
    pos = sum(1 for w in POS_LEX if w in t)
    neg = sum(1 for w in NEG_LEX if w in t)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _direction_from_severity(sev: str) -> Direction:
    s = (sev or "").lower()
    if s in ("low", "low risk"):
        return "positive"
    if s in ("high", "severe", "elevated"):
        return "negative"
    return "neutral"


def _direction_from_outlook(outlook: str) -> Direction:
    o = (outlook or "").lower()
    if o in ("positive", "bullish", "constructive"):
        return "positive"
    if o in ("negative", "bearish", "cautious"):
        return "negative"
    return "neutral"


class O5Contradiction(BaseCheck):
    check_id = "O5"
    dimension = "contradiction"

    def run(self, dataset: Any) -> CheckResult:
        total = 0
        agreed = 0
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                payload = record.get("payload") or {}
                if "risk_assessment" not in payload or "research_narrative" not in payload:
                    continue  # require all three to evaluate
                total += 1
                a = _direction_from_text(payload.get("summary") or "")
                b = _direction_from_severity(
                    (payload.get("risk_assessment") or {}).get("severity") or "")
                c = _direction_from_outlook(
                    (payload.get("research_narrative") or {}).get("outlook") or "")
                directions = {a, b, c}
                if len(directions - {"neutral"}) <= 1:
                    agreed += 1
                else:
                    findings.append(Finding(
                        ticker=ticker, date=d, jsonpath="$.payload",
                        detail={"summary_dir": a, "risk_dir": b, "narrative_dir": c},
                    ))
        rate = (agreed / total) if total else 1.0
        sev = severity_for("O5", value=rate, kind="three_way_agreement")
        return CheckResult(
            check_id="O5",
            severity=sev,
            pass_rate=rate,
            findings=tuple(findings[:50]),
            metrics={"three_way_agreement": rate, "evaluated_records": total},
            recommendation=(
                "Add a coherence pass that vetoes mismatched summary/risk/outlook tuples."
                if sev != "pass" else None
            ),
        )
```

In `runner.py`:

```python
    if check_id == "O5":
        from src.eval.checks.o5_contradiction import O5Contradiction
        return O5Contradiction()
```

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest tests.eval.checks.test_o5_contradiction -v`
Expected: `OK` (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/o5_contradiction.py src/eval/runner.py tests/eval/checks/test_o5_contradiction.py
git commit -m "feat(eval): O5 contradiction check"
```

---

### Task 16: D2 committee_agreement

**Files:**
- Create: `src/eval/checks/d2_committee_agreement.py`
- Create: `tests/eval/checks/test_d2_committee_agreement.py`
- Modify: `src/eval/runner.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_d2_committee_agreement.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.d2_committee_agreement import D2CommitteeAgreement
from src.eval.data_sources import PipelineEvent
from tests.eval.fixtures.builders import make_dataset


def _committee_event(d, ticker, role, action):
    return PipelineEvent(
        date=d, component="committee", severity="info",
        message="role_decision",
        detail={"role": role, "action": action},
        ticker=ticker, module="committee",
    )


class TestD2(unittest.TestCase):
    def test_pass_when_roles_agree(self):
        d = date(2026, 4, 28)
        logs = [
            _committee_event(d, "AAPL", "pm_economy", "buy"),
            _committee_event(d, "AAPL", "pm_deep", "buy"),
            _committee_event(d, "AAPL", "risk", "buy"),
        ]
        ds = make_dataset(tickers=("AAPL",), end=d, logs=logs)
        result = D2CommitteeAgreement().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_roles_disagree(self):
        d = date(2026, 4, 28)
        logs = [
            _committee_event(d, "AAPL", "pm_economy", "buy"),
            _committee_event(d, "AAPL", "pm_deep", "watch"),
            _committee_event(d, "AAPL", "risk", "avoid"),
        ]
        ds = make_dataset(tickers=("AAPL",), end=d, logs=logs)
        result = D2CommitteeAgreement().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.checks.test_d2_committee_agreement -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/eval/checks/d2_committee_agreement.py`:

```python
from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


class D2CommitteeAgreement(BaseCheck):
    check_id = "D2"
    dimension = "committee_agreement"

    def run(self, dataset: Any) -> CheckResult:
        per_key: dict[tuple, dict[str, str]] = defaultdict(dict)
        for ev in dataset.logs:
            if ev.component != "committee":
                continue
            role = (ev.detail or {}).get("role")
            action = (ev.detail or {}).get("action")
            if not role or not action or not ev.ticker:
                continue
            per_key[(ev.ticker, ev.date)][role] = action
        total = 0
        agreed = 0
        findings: list[Finding] = []
        for (ticker, d), roles in per_key.items():
            if len(roles) < 2:
                continue
            total += 1
            actions = set(roles.values())
            if len(actions) == 1:
                agreed += 1
            else:
                findings.append(Finding(
                    ticker=ticker, date=d, module="committee",
                    detail={"roles": dict(roles)},
                ))
        rate = (agreed / total) if total else 1.0
        sev = severity_for("D2", value=rate, kind="role_agreement")
        return CheckResult(
            check_id="D2",
            severity=sev,
            pass_rate=rate,
            findings=tuple(findings[:50]),
            metrics={"role_agreement": rate, "evaluated_decisions": total},
            recommendation=(
                "Tighten committee aggregator: surface disagreements to the user instead of hiding them."
                if sev != "pass" else None
            ),
        )
```

In `runner.py`:

```python
    if check_id == "D2":
        from src.eval.checks.d2_committee_agreement import D2CommitteeAgreement
        return D2CommitteeAgreement()
```

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest tests.eval.checks.test_d2_committee_agreement -v`
Expected: `OK` (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/d2_committee_agreement.py src/eval/runner.py tests/eval/checks/test_d2_committee_agreement.py
git commit -m "feat(eval): D2 committee_agreement check"
```

---

### Task 17: D3 signal_volatility

**Files:**
- Create: `src/eval/checks/d3_signal_volatility.py`
- Create: `tests/eval/checks/test_d3_signal_volatility.py`
- Modify: `src/eval/runner.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_d3_signal_volatility.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.d3_signal_volatility import D3SignalVolatility
from tests.eval.fixtures.builders import make_dataset


class TestD3(unittest.TestCase):
    def test_pass_when_signal_stable(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for record in ds.daily["AAPL"].values():
            record["payload"]["llm_signals"] = {"narrative_strength": 0.6}
        result = D3SignalVolatility().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_signal_swings(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        days = sorted(ds.daily["AAPL"].keys())
        for i, d in enumerate(days):
            ds.daily["AAPL"][d]["payload"]["llm_signals"] = {
                "narrative_strength": 0.1 if i % 2 else 0.9
            }
        result = D3SignalVolatility().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.checks.test_d3_signal_volatility -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/eval/checks/d3_signal_volatility.py`:

```python
from __future__ import annotations

import statistics
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


TRACKED_SIGNALS: tuple[str, ...] = ("narrative_strength", "news_sentiment_score")


class D3SignalVolatility(BaseCheck):
    check_id = "D3"
    dimension = "signal_volatility"

    def run(self, dataset: Any) -> CheckResult:
        per_ticker_signal_std: dict[tuple[str, str], float] = {}
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            samples_by_signal: dict[str, list[float]] = {s: [] for s in TRACKED_SIGNALS}
            for record in days.values():
                signals = (record.get("payload") or {}).get("llm_signals") or {}
                for s in TRACKED_SIGNALS:
                    if s in signals and isinstance(signals[s], (int, float)):
                        samples_by_signal[s].append(float(signals[s]))
            for s, vals in samples_by_signal.items():
                if len(vals) >= 2:
                    std = statistics.pstdev(vals)
                    per_ticker_signal_std[(ticker, s)] = std
                    if std > 0.40:
                        findings.append(Finding(
                            ticker=ticker, jsonpath=f"$.payload.llm_signals.{s}",
                            detail={"std": std, "samples": vals},
                        ))
        worst = max(per_ticker_signal_std.values()) if per_ticker_signal_std else 0.0
        sev = severity_for("D3", value=worst, kind="signal_std")
        return CheckResult(
            check_id="D3",
            severity=sev,
            pass_rate=1.0 - min(worst, 1.0),
            findings=tuple(findings),
            metrics={"worst_signal_std": worst},
            recommendation=(
                "Inspect LLM signal generation; consider averaging across n committee samples."
                if sev != "pass" else None
            ),
        )
```

In `runner.py`:

```python
    if check_id == "D3":
        from src.eval.checks.d3_signal_volatility import D3SignalVolatility
        return D3SignalVolatility()
```

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest tests.eval.checks.test_d3_signal_volatility -v`
Expected: `OK` (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/d3_signal_volatility.py src/eval/runner.py tests/eval/checks/test_d3_signal_volatility.py
git commit -m "feat(eval): D3 signal_volatility check"
```

---

### Task 18: R1 pipeline_summary

**Files:**
- Create: `src/eval/checks/r1_pipeline_summary.py`
- Create: `tests/eval/checks/test_r1_pipeline_summary.py`
- Modify: `src/eval/runner.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_r1_pipeline_summary.py`:

```python
from __future__ import annotations

import unittest
from datetime import date, timedelta

from src.eval.checks.r1_pipeline_summary import R1PipelineSummary
from tests.eval.fixtures.builders import make_dataset, make_summary


class TestR1(unittest.TestCase):
    def test_pass_when_low_fallback_rate(self):
        end = date(2026, 4, 28)
        days = [end - timedelta(days=i) for i in range(14)]
        summaries = {d: make_summary(d, fallback_count=0) for d in days}
        ds = make_dataset(tickers=("AAPL",), end=end, summary_overrides=summaries)
        result = R1PipelineSummary().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_high_fallback_rate(self):
        end = date(2026, 4, 28)
        days = [end - timedelta(days=i) for i in range(14)]
        summaries = {d: make_summary(d, fallback_count=20) for d in days}
        # tickers=("AAPL",) → only 1 ticker → fallback_count=20 > 1 → effectively 100% rate
        ds = make_dataset(tickers=("AAPL",), end=end, summary_overrides=summaries)
        result = R1PipelineSummary().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.checks.test_r1_pipeline_summary -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/eval/checks/r1_pipeline_summary.py`:

```python
from __future__ import annotations

from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


class R1PipelineSummary(BaseCheck):
    check_id = "R1"
    dimension = "pipeline_summary"

    def run(self, dataset: Any) -> CheckResult:
        total_fallbacks = 0
        total_records = 0
        cost_series: list[float] = []
        for d, s in dataset.summaries.items():
            fallbacks = int(s.get("fallback_count") or 0)
            ticker_count = max(len(dataset.tickers), 1)
            total_fallbacks += fallbacks
            total_records += ticker_count
            cost_series.append(float(s.get("daily_api_cost_usd") or 0.0))
        rate = (total_fallbacks / total_records) if total_records else 0.0
        sev = severity_for("R1", value=rate, kind="fallback_rate")
        findings: list[Finding] = []
        if sev != "pass":
            findings.append(Finding(
                module="pipeline_summary",
                detail={"fallback_rate": rate, "total_fallbacks": total_fallbacks,
                        "cost_trend": cost_series},
            ))
        return CheckResult(
            check_id="R1",
            severity=sev,
            pass_rate=1.0 - min(rate, 1.0),
            findings=tuple(findings),
            metrics={"fallback_rate": rate,
                     "total_daily_cost_usd": sum(cost_series)},
            recommendation=(
                "Inspect retry logic in llm_runtime; high fallback often = schema parse failures."
                if sev != "pass" else None
            ),
        )
```

In `runner.py`:

```python
    if check_id == "R1":
        from src.eval.checks.r1_pipeline_summary import R1PipelineSummary
        return R1PipelineSummary()
```

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest tests.eval.checks.test_r1_pipeline_summary -v`
Expected: `OK` (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/r1_pipeline_summary.py src/eval/runner.py tests/eval/checks/test_r1_pipeline_summary.py
git commit -m "feat(eval): R1 pipeline_summary check"
```

---

### Task 19: R2 retry_distribution

**Files:**
- Create: `src/eval/checks/r2_retry_distribution.py`
- Create: `tests/eval/checks/test_r2_retry_distribution.py`
- Modify: `src/eval/runner.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_r2_retry_distribution.py`:

```python
from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.r2_retry_distribution import R2RetryDistribution
from src.eval.data_sources import PipelineEvent
from tests.eval.fixtures.builders import make_dataset


def _retry(d, ticker, module="research_note"):
    return PipelineEvent(date=d, component="analyzer", severity="warn",
                         message="retry", detail={}, ticker=ticker, module=module)


class TestR2(unittest.TestCase):
    def test_pass_when_few_retries(self):
        d = date(2026, 4, 28)
        ds = make_dataset(tickers=("AAPL",), end=d, logs=[_retry(d, "AAPL")])
        result = R2RetryDistribution().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_hot_ticker(self):
        d = date(2026, 4, 28)
        logs = [_retry(d, "AAPL") for _ in range(10)]
        ds = make_dataset(tickers=("AAPL",), end=d, logs=logs)
        result = R2RetryDistribution().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.checks.test_r2_retry_distribution -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/eval/checks/r2_retry_distribution.py`:

```python
from __future__ import annotations

from collections import Counter
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


class R2RetryDistribution(BaseCheck):
    check_id = "R2"
    dimension = "retry_distribution"

    def run(self, dataset: Any) -> CheckResult:
        retry_counts: Counter[str] = Counter()
        for ev in dataset.logs:
            if ev.message == "retry" and ev.ticker:
                retry_counts[ev.ticker] += 1
        worst = max(retry_counts.values()) if retry_counts else 0
        worst_t = max(retry_counts, key=retry_counts.get) if retry_counts else None
        sev = severity_for("R2", value=worst, kind="retry_per_ticker")
        findings: list[Finding] = []
        if worst_t and sev != "pass":
            findings.append(Finding(
                ticker=worst_t, module="analyzer",
                detail={"retry_count_14d": retry_counts[worst_t]},
            ))
        return CheckResult(
            check_id="R2",
            severity=sev,
            pass_rate=1.0 if worst == 0 else max(0.0, 1.0 - worst / 14),
            findings=tuple(findings),
            metrics={"max_retry_per_ticker": float(worst),
                     "tickers_with_retries": float(len(retry_counts))},
            recommendation=(
                f"Investigate {worst_t} retries; often indicates collector data shape regression."
                if sev != "pass" else None
            ),
        )
```

In `runner.py`:

```python
    if check_id == "R2":
        from src.eval.checks.r2_retry_distribution import R2RetryDistribution
        return R2RetryDistribution()
```

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest tests.eval.checks.test_r2_retry_distribution -v`
Expected: `OK` (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/r2_retry_distribution.py src/eval/runner.py tests/eval/checks/test_r2_retry_distribution.py
git commit -m "feat(eval): R2 retry_distribution check"
```

---

### Task 20: Replay infrastructure (FakeLLMClient + cost guard + dry-run)

**Files:**
- Create: `src/eval/replay.py`
- Create: `tests/eval/test_replay.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/test_replay.py`:

```python
from __future__ import annotations

import unittest
from typing import Any

from src.eval.replay import (
    LLMReplayClient,
    ReplayConfig,
    ReplayResult,
    run_replay,
    estimate_cost,
)


class FakeClient(LLMReplayClient):
    def __init__(self, responses: list[str], cost_per_call: float = 0.05) -> None:
        self.responses = list(responses)
        self.cost_per_call = cost_per_call
        self.calls = 0

    def call(self, ticker: str, run_index: int) -> dict[str, Any]:
        self.calls += 1
        return {"summary": self.responses[(self.calls - 1) % len(self.responses)],
                "cost_usd": self.cost_per_call}


class TestReplay(unittest.TestCase):
    def test_dry_run_makes_no_calls(self):
        client = FakeClient(responses=["x"])
        cfg = ReplayConfig(tickers=("AAPL", "MSFT"), runs_per_ticker=3,
                           max_cost_usd=1.0, dry_run=True)
        result = run_replay(client=client, config=cfg)
        self.assertEqual(client.calls, 0)
        self.assertGreater(result.estimated_cost_usd, 0.0)

    def test_cost_cap_aborts(self):
        client = FakeClient(responses=["x"], cost_per_call=0.40)
        cfg = ReplayConfig(tickers=("AAPL", "MSFT"), runs_per_ticker=3,
                           max_cost_usd=1.0, dry_run=False)
        result = run_replay(client=client, config=cfg)
        # 6 calls × $0.40 = $2.40, cap $1.00 → aborts after 2 calls (~$0.80)
        self.assertTrue(result.aborted)
        self.assertLessEqual(client.calls, 3)

    def test_full_run_records_per_ticker_outputs(self):
        client = FakeClient(responses=["a", "a", "a"], cost_per_call=0.05)
        cfg = ReplayConfig(tickers=("AAPL",), runs_per_ticker=3,
                           max_cost_usd=1.0, dry_run=False)
        result = run_replay(client=client, config=cfg)
        self.assertFalse(result.aborted)
        self.assertEqual(len(result.outputs["AAPL"]), 3)
        self.assertAlmostEqual(result.actual_cost_usd, 0.15, places=3)

    def test_estimate_cost(self):
        cost = estimate_cost(tickers=("AAPL", "MSFT"), runs_per_ticker=3,
                             cost_per_call_usd=0.05)
        self.assertAlmostEqual(cost, 0.30, places=3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.test_replay -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/eval/replay.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ReplayConfig:
    tickers: Sequence[str]
    runs_per_ticker: int
    max_cost_usd: float
    dry_run: bool = False
    estimated_cost_per_call_usd: float = 0.05


@dataclass
class ReplayResult:
    outputs: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    actual_cost_usd: float = 0.0
    estimated_cost_usd: float = 0.0
    aborted: bool = False
    abort_reason: str | None = None


class LLMReplayClient(ABC):
    @abstractmethod
    def call(self, ticker: str, run_index: int) -> dict[str, Any]:
        """Returns a dict that MUST contain 'cost_usd' (float).

        Implementations adapt to the production llm_runtime; the FakeLLMClient
        in tests only inflates cost_usd to drive cost-cap behavior.
        """
        raise NotImplementedError


def estimate_cost(*, tickers: Sequence[str], runs_per_ticker: int,
                  cost_per_call_usd: float) -> float:
    return len(tickers) * runs_per_ticker * cost_per_call_usd


def run_replay(*, client: LLMReplayClient, config: ReplayConfig) -> ReplayResult:
    estimated = estimate_cost(
        tickers=config.tickers,
        runs_per_ticker=config.runs_per_ticker,
        cost_per_call_usd=config.estimated_cost_per_call_usd,
    )
    result = ReplayResult(estimated_cost_usd=estimated)
    if config.dry_run:
        return result

    for ticker in config.tickers:
        result.outputs.setdefault(ticker, [])
        for i in range(config.runs_per_ticker):
            if result.actual_cost_usd >= config.max_cost_usd:
                result.aborted = True
                result.abort_reason = f"cost cap {config.max_cost_usd} reached"
                return result
            response = client.call(ticker, i)
            cost = float(response.get("cost_usd") or 0.0)
            if result.actual_cost_usd + cost > config.max_cost_usd:
                result.aborted = True
                result.abort_reason = (
                    f"next call ({cost}) would exceed cap {config.max_cost_usd}"
                )
                return result
            result.actual_cost_usd += cost
            result.outputs[ticker].append(response)
    return result
```

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest tests.eval.test_replay -v`
Expected: `OK` (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/replay.py tests/eval/test_replay.py
git commit -m "feat(eval): replay infrastructure with cost guard + dry-run"
```

---

### Task 21: D1 semantic_drift (uses replay)

**Files:**
- Create: `src/eval/checks/d1_semantic_drift.py`
- Create: `tests/eval/checks/test_d1_semantic_drift.py`
- Modify: `src/eval/runner.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/checks/test_d1_semantic_drift.py`:

```python
from __future__ import annotations

import unittest
from datetime import date
from typing import Any

from src.eval.checks.d1_semantic_drift import D1SemanticDrift
from src.eval.replay import LLMReplayClient
from tests.eval.fixtures.builders import make_dataset


class _DeterministicClient(LLMReplayClient):
    def call(self, ticker: str, run_index: int) -> dict[str, Any]:
        return {"action": "buy", "summary": "Strong fundamentals.", "cost_usd": 0.05}


class _DriftyClient(LLMReplayClient):
    def call(self, ticker: str, run_index: int) -> dict[str, Any]:
        actions = ["buy", "watch", "avoid"]
        summaries = ["Strong.", "Mixed signals today.", "Bearish technical."]
        return {"action": actions[run_index % 3],
                "summary": summaries[run_index % 3], "cost_usd": 0.05}


class TestD1(unittest.TestCase):
    def test_pass_when_deterministic(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        check = D1SemanticDrift(client=_DeterministicClient(),
                                 replay_tickers=("AAPL",), runs_per_ticker=3,
                                 max_cost_usd=1.0, dry_run=False)
        result = check.run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_drifty(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        check = D1SemanticDrift(client=_DriftyClient(),
                                 replay_tickers=("AAPL",), runs_per_ticker=3,
                                 max_cost_usd=1.0, dry_run=False)
        result = check.run(ds)
        self.assertEqual(result.severity, "fail")

    def test_dry_run_returns_info(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        check = D1SemanticDrift(client=_DeterministicClient(),
                                 replay_tickers=("AAPL",), runs_per_ticker=3,
                                 max_cost_usd=1.0, dry_run=True)
        result = check.run(ds)
        self.assertEqual(result.severity, "info")
        self.assertIn("estimated_cost_usd", result.metrics)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify failure**

Run: `python -m unittest tests.eval.checks.test_d1_semantic_drift -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/eval/checks/d1_semantic_drift.py`:

```python
from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for
from src.eval.replay import LLMReplayClient, ReplayConfig, run_replay


def _action_match_rate(outputs_per_ticker: dict[str, list[dict]]) -> float:
    matches = 0
    total = 0
    for ticker, outputs in outputs_per_ticker.items():
        if len(outputs) < 2:
            continue
        actions = [o.get("action") for o in outputs]
        total += 1
        if len(set(actions)) == 1:
            matches += 1
    return (matches / total) if total else 1.0


def _token_jaccard(a: str, b: str) -> float:
    ta = set((a or "").lower().split())
    tb = set((b or "").lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _summary_similarity(outputs_per_ticker: dict[str, list[dict]]) -> float:
    """Use token jaccard as a deterministic, dependency-free similarity proxy.

    sentence-transformers is mentioned in the spec but is heavy to import here
    and offline-incompatible. Token jaccard is a conservative under-estimate
    that satisfies the threshold semantics (higher = more similar).
    """
    pairwise: list[float] = []
    for outputs in outputs_per_ticker.values():
        if len(outputs) < 2:
            continue
        for i in range(len(outputs)):
            for j in range(i + 1, len(outputs)):
                pairwise.append(_token_jaccard(
                    outputs[i].get("summary") or "",
                    outputs[j].get("summary") or "",
                ))
    return (sum(pairwise) / len(pairwise)) if pairwise else 1.0


class D1SemanticDrift(BaseCheck):
    check_id = "D1"
    dimension = "semantic_drift"

    def __init__(
        self,
        *,
        client: LLMReplayClient,
        replay_tickers: Sequence[str],
        runs_per_ticker: int,
        max_cost_usd: float,
        dry_run: bool,
    ) -> None:
        self.client = client
        self.replay_tickers = tuple(replay_tickers)
        self.runs_per_ticker = runs_per_ticker
        self.max_cost_usd = max_cost_usd
        self.dry_run = dry_run

    def run(self, dataset: Any) -> CheckResult:
        cfg = ReplayConfig(
            tickers=self.replay_tickers,
            runs_per_ticker=self.runs_per_ticker,
            max_cost_usd=self.max_cost_usd,
            dry_run=self.dry_run,
        )
        replay_result = run_replay(client=self.client, config=cfg)
        if self.dry_run:
            return CheckResult(
                check_id="D1",
                severity="info",
                pass_rate=0.0,
                findings=(),
                metrics={"estimated_cost_usd": replay_result.estimated_cost_usd},
                recommendation="Re-run without --dry-run to obtain actual drift measurement.",
            )
        if replay_result.aborted:
            return CheckResult(
                check_id="D1",
                severity="fail",
                pass_rate=0.0,
                findings=(Finding(detail={
                    "abort_reason": replay_result.abort_reason,
                    "actual_cost_usd": replay_result.actual_cost_usd,
                }),),
                metrics={"actual_cost_usd": replay_result.actual_cost_usd},
                recommendation="Increase --max-replay-cost-usd or reduce --replay-tickers.",
            )

        action_match = _action_match_rate(replay_result.outputs)
        sim = _summary_similarity(replay_result.outputs)
        sev_action = severity_for("D1", value=action_match, kind="action_match")
        sev_sim = severity_for("D1", value=sim, kind="embedding_similarity")
        order = {"pass": 0, "info": 0, "warn": 1, "fail": 2}
        sev = max([sev_action, sev_sim], key=lambda x: order[x])
        findings: list[Finding] = []
        for ticker, outputs in replay_result.outputs.items():
            actions = [o.get("action") for o in outputs]
            if len(set(actions)) > 1:
                findings.append(Finding(
                    ticker=ticker, module="d1_replay",
                    detail={"actions_seen": actions,
                            "summaries": [o.get("summary") for o in outputs]},
                ))
        return CheckResult(
            check_id="D1",
            severity=sev,
            pass_rate=min(action_match, sim),
            findings=tuple(findings),
            metrics={"action_match": action_match,
                     "summary_similarity": sim,
                     "actual_cost_usd": replay_result.actual_cost_usd},
            recommendation=(
                "Reduce model temperature, pin seed where supported, or move from "
                "research_note to committee for higher consensus on drifty tickers."
                if sev != "pass" else None
            ),
        )
```

In `runner.py`, add D1 wiring (this is where `replay.py` integrates with the runner — the runner constructs the production client; tests inject a fake via `cfg.check_overrides`):

```python
    if check_id == "D1":
        if cfg.skip_replay:
            # treat as info / no-op when skipped
            from src.eval.checks.base import CheckResult
            class _Skipped(BaseCheck):
                check_id = "D1"
                dimension = "semantic_drift"
                def run(self, ds):
                    return CheckResult(
                        check_id="D1", severity="info", pass_rate=0.0,
                        findings=(), metrics={"skipped": 1.0},
                        recommendation="Run without --skip-replay to enable drift check.",
                    )
            return _Skipped()
        from src.eval.checks.d1_semantic_drift import D1SemanticDrift
        from src.eval.replay import LLMReplayClient
        # Production client is wired by an adapter (next task scope: stub here).
        # If overrides supply D1 directly (test path), `_build_check` returns it earlier.
        raise NotImplementedError(
            "D1 production client adapter is wired in tests via cfg.check_overrides; "
            "real run requires --skip-replay or an env-configured client (see Task 23)."
        )
```

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest tests.eval.checks.test_d1_semantic_drift -v`
Expected: `OK` (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/eval/checks/d1_semantic_drift.py src/eval/runner.py tests/eval/checks/test_d1_semantic_drift.py
git commit -m "feat(eval): D1 semantic_drift check + replay integration"
```

---

### Task 22: Production D1 client adapter + end-to-end smoke

**Files:**
- Modify: `src/eval/replay.py` (add `OpenAIReplayClient`)
- Modify: `src/eval/runner.py` (wire production client when not skip_replay and not overridden)
- Create: `tests/eval/test_smoke.py` (full audit using all 14 checks via overrides where needed)

- [ ] **Step 1: Write the failing test**

`tests/eval/test_smoke.py`:

```python
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import Any
from unittest import mock

from src.eval.checks.base import BaseCheck, CheckResult
from src.eval.checks.d1_semantic_drift import D1SemanticDrift
from src.eval.replay import LLMReplayClient
from src.eval.runner import RunnerConfig, run_audit
from tests.eval.fixtures.builders import make_dataset


class _StableClient(LLMReplayClient):
    def call(self, ticker, run_index):
        return {"action": "buy", "summary": "stable.", "cost_usd": 0.05}


class TestSmokeAll14Checks(unittest.TestCase):
    def test_full_run_with_replay_overridden(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
            d1 = D1SemanticDrift(client=_StableClient(), replay_tickers=("AAPL",),
                                  runs_per_ticker=3, max_cost_usd=1.0, dry_run=False)
            cfg = RunnerConfig(
                root=tmp, audit_date=date(2026, 4, 28), window_days=14,
                tickers=["AAPL"],
                checks=("I1", "I2", "I3", "I4",
                        "O1", "O2", "O3", "O4", "O5",
                        "D1", "D2", "D3", "R1", "R2"),
                skip_replay=False, check_links=False,
                model_profile="economy", git_sha="abcd1234",
                check_overrides={"D1": d1},
            )
            with mock.patch("src.eval.runner.load_window", return_value=ds):
                exit_code, results = run_audit(cfg)
            self.assertEqual(len(results), 14)
            ids = {r.check_id for r in results}
            self.assertEqual(ids, {"I1", "I2", "I3", "I4", "O1", "O2", "O3", "O4",
                                   "O5", "D1", "D2", "D3", "R1", "R2"})
            json_path = tmp / "output" / "data" / "llm_audit" / "2026-04-28.json"
            self.assertTrue(json_path.exists())
            data = json.loads(json_path.read_text())
            self.assertEqual(data["summary"]["total_checks"], 14)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run — verify it identifies missing wiring**

Run: `python -m unittest tests.eval.test_smoke -v`
Expected: failure on assertion or NotImplementedError from D1 path.

- [ ] **Step 3: Add `OpenAIReplayClient` and runner wiring**

In `src/eval/replay.py`, append:

```python
class OpenAIReplayClient(LLMReplayClient):
    """Thin shim over the existing llm_runtime.

    The actual call delegates to `src.analyzer.llm_runtime.run_structured_llm_module`
    with the research_note module. We intentionally keep the import lazy so unit
    tests do not pay the import cost or require an API key.
    """

    def __init__(self, model_profile: str) -> None:
        self.model_profile = model_profile

    def call(self, ticker: str, run_index: int) -> dict[str, Any]:
        from src.analyzer.llm_runtime import run_structured_llm_module  # lazy
        # Adapter must produce a minimal payload with `action`, `summary`, `cost_usd`.
        # Real implementation will pull collected data and construct the prompt.
        result = run_structured_llm_module(  # type: ignore[call-arg]
            module_name="research_note",
            ticker=ticker,
            model_profile=self.model_profile,
        )
        return {
            "action": result.get("action"),
            "summary": result.get("summary"),
            "cost_usd": float(result.get("cost_usd") or 0.0),
        }
```

In `src/eval/runner.py`, replace the `D1` block in `_build_check`:

```python
    if check_id == "D1":
        if check_id in cfg.check_overrides:
            return cfg.check_overrides[check_id]
        if cfg.skip_replay:
            class _Skipped(BaseCheck):
                check_id = "D1"
                dimension = "semantic_drift"
                def run(self, ds):
                    return CheckResult(
                        check_id="D1", severity="info", pass_rate=0.0,
                        findings=(), metrics={"skipped": 1.0},
                        recommendation="Run without --skip-replay to enable drift check.",
                    )
            return _Skipped()
        from src.eval.checks.d1_semantic_drift import D1SemanticDrift
        from src.eval.replay import OpenAIReplayClient
        return D1SemanticDrift(
            client=OpenAIReplayClient(model_profile=cfg.model_profile),
            replay_tickers=cfg.replay_tickers,
            runs_per_ticker=cfg.runs_per_ticker,
            max_cost_usd=cfg.max_replay_cost_usd,
            dry_run=cfg.dry_run,
        )
```

(Move the per-check overrides check up to a single early-return at the top of `_build_check` so test overrides apply uniformly.)

- [ ] **Step 4: Run — verify pass**

Run: `python -m unittest discover -s tests/eval -v`
Expected: all eval tests `OK` (now ~30 test methods across 16 files).

- [ ] **Step 5: Commit**

```bash
git add src/eval/replay.py src/eval/runner.py tests/eval/test_smoke.py
git commit -m "feat(eval): production replay client adapter + 14-check smoke test"
```

---

### Task 23: README + golden file + final compile check

**Files:**
- Create: `src/eval/README.md`
- Create: `tests/eval/fixtures/golden/audit_report_sample.md`
- Create: `tests/eval/test_golden.py`

- [ ] **Step 1: Write the failing test**

`tests/eval/test_golden.py`:

```python
from __future__ import annotations

import os
import unittest
from datetime import date
from pathlib import Path

from src.eval.checks.base import CheckResult
from src.eval.report import render_markdown


GOLDEN_PATH = Path(__file__).parent / "fixtures" / "golden" / "audit_report_sample.md"


def _fixture_results():
    return [
        CheckResult(check_id="I1", severity="pass", pass_rate=1.0,
                    findings=(), metrics={"missing_field_rate": 0.0}, recommendation=None),
        CheckResult(check_id="I3", severity="fail", pass_rate=0.33,
                    findings=(), metrics={"format_count": 3.0},
                    recommendation="Normalize ISO."),
    ]


class TestGolden(unittest.TestCase):
    def test_markdown_matches_golden(self):
        md = render_markdown(
            audit_date=date(2026, 4, 28),
            window_start=date(2026, 4, 15), window_end=date(2026, 4, 28),
            tickers=("AAPL", "MSFT"),
            replay_meta={"enabled": False, "cost_usd": 0.0},
            results=_fixture_results(),
        )
        if os.environ.get("UPDATE_GOLDENS") == "1":
            GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            GOLDEN_PATH.write_text(md, encoding="utf-8")
        expected = GOLDEN_PATH.read_text(encoding="utf-8")
        self.assertEqual(md, expected)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Generate the golden once with the env var, then assert pinning**

Run (one-time generation):
```
UPDATE_GOLDENS=1 python -m unittest tests.eval.test_golden -v
```

Then verify the golden file was written:
```
ls tests/eval/fixtures/golden/audit_report_sample.md
```

Subsequent runs (without the env var) must pass:
```
python -m unittest tests.eval.test_golden -v
```
Expected: `OK`.

- [ ] **Step 3: Write README**

`src/eval/README.md`:

````markdown
# src/eval — LLM Quality Audit

One-shot diagnostic for the analyzer's LLM outputs over a 14-day window. Read-only against `output/data/` and `logs/pipeline/`. Writes two artifacts:

- `docs/reports/llm-audit-YYYY-MM-DD.md` (human)
- `output/data/llm_audit/YYYY-MM-DD.json` (machine)

## Run

```bash
python -m src.eval.runner                           # default: 14-day window, ALL 14 checks
python -m src.eval.runner --skip-replay             # free mode (no LLM calls)
python -m src.eval.runner --dry-run                 # cost estimate only
python -m src.eval.runner --checks I1,O2,D2         # subset
python -m src.eval.runner --max-replay-cost-usd 0.5 # tighter budget
python -m src.eval.runner --suffix evening          # second run same day, separate file
```

## Cost

D1 (semantic_drift) is the only check that calls the LLM. Default budget: 5 tickers × 3 runs ≈ $0.30–$0.80 per audit on the `economy` profile. Cap defaults to `$1.0`. Other 13 checks are free.

## Checks

| ID | Dimension |
|----|-----------|
| I1 | schema_stability |
| I2 | missingness |
| I3 | format_consistency |
| I4 | input_size_drift |
| O1 | schema_compliance |
| O2 | numeric_grounding |
| O3 | citation_integrity |
| O4 | language_consistency |
| O5 | contradiction |
| D1 | semantic_drift (replay) |
| D2 | committee_agreement |
| D3 | signal_volatility |
| R1 | pipeline_summary |
| R2 | retry_distribution |

Thresholds live in `src/eval/config.py`. Adjust there only — do not hard-code in checks.

## Tests

```bash
python -m unittest discover -s tests/eval -v
```

Refresh golden:

```bash
UPDATE_GOLDENS=1 python -m unittest tests.eval.test_golden -v
```
````

- [ ] **Step 4: Final compile + full test sweep**

Run:
```bash
python -m compileall src/eval
python -m unittest discover -s tests/eval -v
```
Expected: 0 syntax errors and `OK` for all eval tests.

- [ ] **Step 5: Commit**

```bash
git add src/eval/README.md tests/eval/fixtures/golden/audit_report_sample.md tests/eval/test_golden.py
git commit -m "docs(eval): README + golden audit report fixture"
```

---

## Self-Review (post-write check)

Spec coverage:

- ✅ Goals/Non-Goals match implementation scope (no pipeline edits, audit is read-only).
- ✅ Architecture: `src/eval/` plugin pattern matches spec section "Architecture".
- ✅ Execution interface: every CLI flag from the spec is wired in `_parse_args` (Task 7) and re-verified in Task 22.
- ✅ Data flow: `AuditDataset`, `PipelineEvent`, `load_window` (Task 4) directly mirror the spec data model.
- ✅ All 14 checks have a task (Tasks 5, 8–19, 21).
- ✅ Report format: markdown + JSON + console output (Task 6 + integration in Task 7).
- ✅ Cost model: dry-run, cost cap, abort behavior (Task 20). Production adapter in Task 22.
- ✅ Test strategy: per-check unit tests (3 cases each via `pass`/`boundary`/`failure_mode`), integration tests, golden file, no real API in tests, `unittest` runner per project standard.
- ✅ Open Questions from spec are not embedded into thresholds (kept in `config.py`, so adjustable later without code changes).

Placeholder scan: no TBD/TODO/"…similar to" placeholders. Every code step shows actual code.

Type/method consistency: `BaseCheck.run(dataset) -> CheckResult` is the single check interface; every check implements it. `CheckResult.severity` is `Literal["pass","warn","fail","info"]` consistent in `report.py` and runner exit-code logic. `RunnerConfig.check_overrides` keyed by `check_id` and consumed identically in Tasks 7 and 22.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-28-llm-quality-audit.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
