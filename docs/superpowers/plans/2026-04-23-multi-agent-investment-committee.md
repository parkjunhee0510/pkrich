# Multi-Agent Investment Committee Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an analyzer-stage multi-agent investment committee that runs independent role-based LLM calls for every ticker, selectively reruns Risk/Macro/PM with `deep`, and shows committee output in default JSON and Markdown outputs while keeping the rule-based decision layer as the official `buy/watch/avoid` source of truth.

**Architecture:** Extend the analyzer flow with a dedicated committee orchestrator that consumes finalized `TickerAnalysis` inputs and emits a schema-stable `committee_analysis` payload. Wire committee execution into the existing pipeline after ensemble analysis, serialize the new payload through JSON and Markdown output layers, and keep cost and escalation behavior configurable through `config/models.yaml`.

**Tech Stack:** Python 3.11, dataclasses, existing analyzer/orchestrator runtime, YAML model config, unittest, JSON/Markdown exporters

---

## File Structure

### Create

- `src/analyzer/committee.py`
  Responsibility: committee dataclasses, stance mapping helpers, escalation logic, and orchestration entrypoint
- `src/analyzer/committee_prompt.py`
  Responsibility: build role-specific prompt payloads and enforce concise role contracts
- `tests/test_committee.py`
  Responsibility: unit tests for schema, escalation triggers, and mapping helpers
- `tests/test_committee_output.py`
  Responsibility: JSON and Markdown serialization coverage for committee output

### Modify

- `src/types.py`
  Responsibility: extend `TickerAnalysis` with `committee_analysis`
- `src/pipeline.py`
  Responsibility: run committee flow after ensemble analysis and before output serialization
- `src/output/json_export.py`
  Responsibility: include committee payload in ticker JSON
- `src/output/markdown.py`
  Responsibility: render committee sections in daily and per-ticker Markdown
- `src/utils/model_config.py`
  Responsibility: load committee config from `config/models.yaml`
- `config/models.yaml`
  Responsibility: declare committee defaults and thresholds
- `docs/analyzer.md`
  Responsibility: document new committee subflow
- `docs/output.md`
  Responsibility: document committee output in default artifacts
- `docs/cost.md`
  Responsibility: document economy-first plus selective deep rerun cost policy

### Existing Tests To Run

- `tests/test_analysis_ensemble.py`
- `tests/test_pipeline_quality_wiring.py`
- `tests/test_output.py`
- `tests/test_output_schema.py`

---

### Task 1: Define Committee Types And Mapping Rules

**Files:**
- Modify: `src/types.py`
- Create: `src/analyzer/committee.py`
- Test: `tests/test_committee.py`

- [ ] **Step 1: Write the failing type-and-mapping tests**

```python
import unittest

from src.analyzer.committee import (
    committee_stance_to_action,
    default_committee_analysis,
    should_trigger_deep_committee_review,
)


class CommitteeCoreTests(unittest.TestCase):
    def test_committee_stance_maps_to_existing_action_scale(self) -> None:
        self.assertEqual(committee_stance_to_action("strong_buy"), "buy")
        self.assertEqual(committee_stance_to_action("buy"), "buy")
        self.assertEqual(committee_stance_to_action("watch"), "watch")
        self.assertEqual(committee_stance_to_action("reduce"), "avoid")
        self.assertEqual(committee_stance_to_action("avoid"), "avoid")

    def test_default_committee_payload_is_schema_stable(self) -> None:
        payload = default_committee_analysis()
        self.assertEqual(payload["status"], "not_run")
        self.assertFalse(payload["deep_review_triggered"])
        self.assertIn("roles", payload)
        self.assertIn("pm", payload["roles"])

    def test_deep_review_triggers_on_pm_low_confidence(self) -> None:
        payload = {
            "roles": {
                "risk_manager": {"strong_objection": False},
                "macro_strategist": {"strong_objection": False},
                "pm": {"confidence": 0.41},
            }
        }
        triggered, reasons = should_trigger_deep_committee_review(payload, pm_threshold=0.5)
        self.assertTrue(triggered)
        self.assertEqual(reasons, ["pm_low_confidence"])
```

- [ ] **Step 2: Run the focused tests to confirm failure**

Run: `python -m unittest tests.test_committee -v`
Expected: FAIL with `ModuleNotFoundError` for `src.analyzer.committee` and missing `committee_analysis` support in `TickerAnalysis`

- [ ] **Step 3: Add minimal committee helpers and type support**

```python
# src/analyzer/committee.py
from __future__ import annotations

from typing import Any


_ROLE_KEYS = (
    "growth_analyst",
    "value_skeptic",
    "risk_manager",
    "macro_strategist",
    "pm",
)


def default_committee_analysis() -> dict[str, Any]:
    return {
        "status": "not_run",
        "agreement_status": "not_applicable",
        "deep_review_triggered": False,
        "deep_review_reasons": [],
        "roles": {
            role: {
                "stance": "watch",
                "summary": "",
            }
            for role in _ROLE_KEYS
        },
    }


def committee_stance_to_action(stance: str) -> str:
    mapping = {
        "strong_buy": "buy",
        "buy": "buy",
        "watch": "watch",
        "reduce": "avoid",
        "avoid": "avoid",
    }
    return mapping.get(str(stance).strip().lower(), "watch")


def should_trigger_deep_committee_review(
    committee_payload: dict[str, Any],
    *,
    pm_threshold: float,
) -> tuple[bool, list[str]]:
    roles = committee_payload.get("roles", {})
    reasons: list[str] = []
    pm_confidence = float(roles.get("pm", {}).get("confidence", 1.0) or 0.0)
    if pm_confidence < pm_threshold:
        reasons.append("pm_low_confidence")
    if bool(roles.get("risk_manager", {}).get("strong_objection", False)):
        reasons.append("risk_strong_objection")
    if bool(roles.get("macro_strategist", {}).get("strong_objection", False)):
        reasons.append("macro_strong_objection")
    return bool(reasons), reasons
```

```python
# src/types.py
@dataclass(frozen=True)
class TickerAnalysis:
    ...
    analysis_consensus: dict[str, object] = field(default_factory=dict)
    committee_analysis: dict[str, object] = field(default_factory=dict)
    historical_prices: list[dict[str, str]] = field(default_factory=list)
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `python -m unittest tests.test_committee -v`
Expected: PASS for the new helper and type coverage

- [ ] **Step 5: Commit**

```bash
git add src/types.py src/analyzer/committee.py tests/test_committee.py
git commit -m "feat: add committee core types and mapping helpers"
```

---

### Task 2: Load Committee Config From Models YAML

**Files:**
- Modify: `src/utils/model_config.py`
- Modify: `config/models.yaml`
- Test: `tests/test_model_config.py`

- [ ] **Step 1: Write the failing config test**

```python
def test_load_committee_config_reads_defaults(self) -> None:
    config_path.write_text(
        "\n".join(
            [
                "default_profile: economy",
                "committee:",
                "  enabled: true",
                "  economy_model: economy",
                "  deep_model: deep",
                "  pm_low_confidence_threshold: 0.55",
                "  max_summary_sentences_per_role: 2",
                "profiles:",
                "  economy:",
                "    model: gpt-5.4-mini",
                "  deep:",
                "    model: o3-mini",
            ]
        ),
        encoding='utf-8',
    )
    committee = load_committee_config(str(config_path))
    self.assertTrue(committee.enabled)
    self.assertEqual(committee.economy_model, "economy")
    self.assertEqual(committee.deep_model, "deep")
    self.assertAlmostEqual(committee.pm_low_confidence_threshold, 0.55)
```

- [ ] **Step 2: Run the config test to verify failure**

Run: `python -m unittest tests.test_model_config.LoadModelConfigTests.test_load_committee_config_reads_defaults -v`
Expected: FAIL with `NameError` or `ImportError` because `load_committee_config` does not exist

- [ ] **Step 3: Add the config dataclass and loader**

```python
# src/utils/model_config.py
@dataclass(frozen=True)
class CommitteeConfig:
    enabled: bool
    economy_model: str
    deep_model: str
    pm_low_confidence_threshold: float
    max_summary_sentences_per_role: int
    max_summary_sentences_for_pm: int


def load_committee_config(path: str = 'config/models.yaml') -> CommitteeConfig:
    config = _load_model_config(path)
    committee = config.get('committee', {}) or {}
    profiles = config.get('profiles', {}) or {}
    economy_model = str(committee.get('economy_model', 'economy')).strip() or 'economy'
    deep_model = str(committee.get('deep_model', 'deep')).strip() or 'deep'
    if economy_model not in profiles:
        raise ValueError(f'committee.economy_model must reference a configured profile: {economy_model}')
    if deep_model not in profiles:
        raise ValueError(f'committee.deep_model must reference a configured profile: {deep_model}')
    return CommitteeConfig(
        enabled=bool(committee.get('enabled', True)),
        economy_model=economy_model,
        deep_model=deep_model,
        pm_low_confidence_threshold=float(committee.get('pm_low_confidence_threshold', 0.55)),
        max_summary_sentences_per_role=int(committee.get('max_summary_sentences_per_role', 2)),
        max_summary_sentences_for_pm=int(committee.get('max_summary_sentences_for_pm', 3)),
    )
```

```yaml
# config/models.yaml
committee:
  enabled: true
  economy_model: economy
  deep_model: deep
  pm_low_confidence_threshold: 0.55
  max_summary_sentences_per_role: 2
  max_summary_sentences_for_pm: 3
```

- [ ] **Step 4: Run the config tests**

Run: `python -m unittest tests.test_model_config -v`
Expected: PASS for the new committee loader and existing ensemble/profile tests

- [ ] **Step 5: Commit**

```bash
git add src/utils/model_config.py config/models.yaml tests/test_model_config.py
git commit -m "feat: add committee config loader"
```

---

### Task 3: Build Committee Orchestrator And Escalation Flow

**Files:**
- Create: `src/analyzer/committee_prompt.py`
- Modify: `src/analyzer/committee.py`
- Test: `tests/test_committee.py`

- [ ] **Step 1: Write the failing orchestration tests**

```python
def test_run_committee_analysis_builds_all_role_outputs(self) -> None:
    runner = _FakeCommitteeRunner()
    analysis = _make_analysis("AAPL")
    payload = run_committee_analysis(
        analysis,
        collected=_make_collected("AAPL"),
        macro_context={"market_regime": {"regime": "neutral"}},
        economy_profile_name="economy",
        deep_profile_name="deep",
        pm_low_confidence_threshold=0.55,
        role_runner=runner,
    )
    self.assertEqual(payload["status"], "economy_only")
    self.assertIn("growth_analyst", payload["roles"])
    self.assertEqual(payload["roles"]["pm"]["stance"], "buy")

def test_run_committee_analysis_reruns_only_risk_macro_pm_when_escalated(self) -> None:
    runner = _FakeCommitteeRunner(pm_confidence=0.40, risk_strong_objection=True)
    payload = run_committee_analysis(...)
    self.assertTrue(payload["deep_review_triggered"])
    self.assertEqual(runner.deep_roles, ["risk_manager", "macro_strategist", "pm"])
```

- [ ] **Step 2: Run the orchestration tests to verify failure**

Run: `python -m unittest tests.test_committee.CommitteeOrchestratorTests -v`
Expected: FAIL because `run_committee_analysis` and prompt builders are not implemented

- [ ] **Step 3: Implement prompt builders and orchestration**

```python
# src/analyzer/committee_prompt.py
from __future__ import annotations

from typing import Any


def build_role_prompt(role: str, analysis_payload: dict[str, Any], *, max_sentences: int) -> dict[str, str]:
    role_instructions = {
        "growth_analyst": "You are a growth-stock bull. Focus on upside, catalysts, and durability.",
        "value_skeptic": "You are a valuation skeptic. Focus on expectation risk, multiple risk, and narrative excess.",
        "risk_manager": "You are a risk manager. Focus only on downside, invalidation, and drawdown risk.",
        "macro_strategist": "You are a macro strategist. Focus only on rates, FX, liquidity, and macro regime pressure.",
        "pm": "You are the portfolio manager. Synthesize the other role outputs and issue the final committee stance.",
    }
    return {
        "system": role_instructions[role],
        "user": (
            f"Return JSON only. Keep summary within {max_sentences} sentences. "
            f"Use stance from strong_buy, buy, watch, reduce, avoid. "
            f"Context: {analysis_payload}"
        ),
    }
```

```python
# src/analyzer/committee.py
def run_committee_analysis(
    analysis: TickerAnalysis,
    *,
    collected: CollectedTickerData,
    macro_context: dict[str, Any],
    economy_profile_name: str,
    deep_profile_name: str,
    pm_low_confidence_threshold: float,
    role_runner,
    max_role_sentences: int = 2,
    max_pm_sentences: int = 3,
) -> dict[str, Any]:
    payload = default_committee_analysis()
    analysis_payload = {
        "ticker": analysis.ticker,
        "summary": analysis.summary,
        "signal_or_takeaway": analysis.signal_or_takeaway,
        "data_snapshot": analysis.data_snapshot,
        "macro_context": macro_context,
        "collected_price": collected.price,
    }
    ordered_roles = ["growth_analyst", "value_skeptic", "risk_manager", "macro_strategist"]
    for role in ordered_roles:
        prompt = build_role_prompt(role, analysis_payload, max_sentences=max_role_sentences)
        payload["roles"][role] = role_runner(role, prompt, model_profile_name=economy_profile_name)
    pm_prompt = build_role_prompt("pm", {**analysis_payload, "roles": payload["roles"]}, max_sentences=max_pm_sentences)
    payload["roles"]["pm"] = role_runner("pm", pm_prompt, model_profile_name=economy_profile_name)
    triggered, reasons = should_trigger_deep_committee_review(payload, pm_threshold=pm_low_confidence_threshold)
    payload["deep_review_triggered"] = triggered
    payload["deep_review_reasons"] = reasons
    payload["status"] = "deep_reviewed" if triggered else "economy_only"
    if triggered:
        for role in ("risk_manager", "macro_strategist", "pm"):
            prompt = build_role_prompt(role, {**analysis_payload, "roles": payload["roles"]}, max_sentences=max_pm_sentences if role == "pm" else max_role_sentences)
            payload["roles"][role] = role_runner(role, prompt, model_profile_name=deep_profile_name)
    payload["agreement_status"] = _derive_agreement_status(payload["roles"])
    return payload
```

- [ ] **Step 4: Run the new and existing committee tests**

Run: `python -m unittest tests.test_committee -v`
Expected: PASS for mapping, escalation, and orchestration behavior

- [ ] **Step 5: Commit**

```bash
git add src/analyzer/committee.py src/analyzer/committee_prompt.py tests/test_committee.py
git commit -m "feat: add committee orchestration and deep escalation"
```

---

### Task 4: Wire Committee Execution Into The Pipeline

**Files:**
- Modify: `src/pipeline.py`
- Test: `tests/test_pipeline_quality_wiring.py`
- Test: `tests/test_committee.py`

- [ ] **Step 1: Write the failing pipeline wiring test**

```python
def test_run_pipeline_attaches_committee_analysis_to_analyses(self) -> None:
    committee_payload = {
        "status": "economy_only",
        "agreement_status": "mixed",
        "deep_review_triggered": False,
        "deep_review_reasons": [],
        "roles": {"pm": {"stance": "watch", "summary": "mixed setup", "confidence": 0.61}},
    }
    with ExitStack() as stack:
        ...
        mock_committee = stack.enter_context(patch("src.pipeline.run_committee_batch"))
        mock_committee.return_value = {"AAPL": committee_payload}
        run_pipeline(run_date=date(2026, 4, 8))
    analyses = captured["analyses"]
    self.assertEqual(analyses[0].committee_analysis["status"], "economy_only")
```

- [ ] **Step 2: Run the wiring test to verify failure**

Run: `python -m unittest tests.test_pipeline_quality_wiring -v`
Expected: FAIL because the pipeline does not attach committee payloads

- [ ] **Step 3: Add batch execution and attachment in the pipeline**

```python
# src/pipeline.py
from src.analyzer.committee import default_committee_analysis, run_committee_batch
from src.utils.model_config import load_committee_config

...
committee_config = load_committee_config()
committee_by_ticker = run_committee_batch(
    analyses,
    collected=collected,
    macro_context=macro_context or {},
    config=committee_config,
    logger=get_pipeline_logger(),
)
analyses = [
    replace(
        analysis,
        committee_analysis=committee_by_ticker.get(analysis.ticker, default_committee_analysis()),
    )
    for analysis in analyses
]
```

- [ ] **Step 4: Run wiring and pipeline-adjacent tests**

Run: `python -m unittest tests.test_pipeline_quality_wiring tests.test_analysis_ensemble -v`
Expected: PASS with committee payload attached and existing ensemble flow still intact

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline_quality_wiring.py tests/test_committee.py
git commit -m "feat: wire committee analysis into pipeline"
```

---

### Task 5: Serialize Committee Output In JSON And Markdown

**Files:**
- Modify: `src/output/json_export.py`
- Modify: `src/output/markdown.py`
- Test: `tests/test_committee_output.py`
- Test: `tests/test_output.py`

- [ ] **Step 1: Write the failing serialization tests**

```python
def test_serialize_analysis_includes_committee_payload(self) -> None:
    analysis = _make_analysis(
        ticker="AAPL",
        committee_analysis={
            "status": "economy_only",
            "agreement_status": "mixed",
            "deep_review_triggered": False,
            "deep_review_reasons": [],
            "roles": {
                "growth_analyst": {"stance": "buy", "summary": "growth intact"},
                "pm": {"stance": "watch", "summary": "wait for confirmation", "confidence": 0.61},
            },
        },
    )
    payload = _serialize_analysis(analysis, {"7d": "N/A", "30d": "N/A"})
    self.assertIn("committee_analysis", payload)
    self.assertEqual(payload["committee_analysis"]["roles"]["pm"]["stance"], "watch")

def test_render_ticker_markdown_includes_committee_section(self) -> None:
    markdown = render_ticker_markdown(_make_analysis_with_committee("AAPL"))
    self.assertIn("## 투자 위원회", markdown)
    self.assertIn("Growth Analyst", markdown)
    self.assertIn("PM", markdown)
```

- [ ] **Step 2: Run output tests to verify failure**

Run: `python -m unittest tests.test_committee_output tests.test_output -v`
Expected: FAIL because JSON and Markdown do not render committee data

- [ ] **Step 3: Implement serialization and rendering**

```python
# src/output/json_export.py
result: dict[str, Any] = {
    ...
    "analysis_consensus": getattr(analysis, "analysis_consensus", {}),
    "committee_analysis": getattr(analysis, "committee_analysis", {}),
    "period_changes": period_changes,
    ...
}
```

```python
# src/output/markdown.py
def _render_committee_section(committee: dict[str, Any]) -> str:
    if not committee:
        return "- 위원회 데이터가 없습니다."
    roles = committee.get("roles", {})
    lines = [
        f"- 합의 상태: {committee.get('agreement_status', 'N/A')}",
        f"- Deep 재심: {'예' if committee.get('deep_review_triggered') else '아니오'}",
        f"- Growth Analyst: {roles.get('growth_analyst', {}).get('summary', 'N/A')}",
        f"- Value Skeptic: {roles.get('value_skeptic', {}).get('summary', 'N/A')}",
        f"- Risk Manager: {roles.get('risk_manager', {}).get('summary', 'N/A')}",
        f"- Macro Strategist: {roles.get('macro_strategist', {}).get('summary', 'N/A')}",
        f"- PM: {roles.get('pm', {}).get('summary', 'N/A')}",
    ]
    return "\n".join(lines)
```

```python
# src/output/markdown.py inside render_ticker_markdown()
"## 투자 위원회",
_render_committee_section(getattr(analysis, "committee_analysis", {})),
"",
```

- [ ] **Step 4: Run the serialization tests**

Run: `python -m unittest tests.test_committee_output tests.test_output -v`
Expected: PASS for committee JSON fields and Markdown sections

- [ ] **Step 5: Commit**

```bash
git add src/output/json_export.py src/output/markdown.py tests/test_committee_output.py tests/test_output.py
git commit -m "feat: render committee analysis in outputs"
```

---

### Task 6: Update Docs And Regression Coverage

**Files:**
- Modify: `docs/analyzer.md`
- Modify: `docs/output.md`
- Modify: `docs/cost.md`
- Test: `tests/test_output_schema.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing schema regression test**

```python
def test_dashboard_shape_includes_committee_analysis(self) -> None:
    payload = _serialize_analysis(_make_analysis_with_committee("AAPL"), {"7d": "N/A", "30d": "N/A"})
    self.assertIn("committee_analysis", payload)
    self.assertIn("roles", payload["committee_analysis"])
```

- [ ] **Step 2: Run regression tests to verify current failure surface**

Run: `python -m unittest tests.test_output_schema tests.test_pipeline -v`
Expected: FAIL until committee payload is documented in output shape and pipeline serialization remains stable

- [ ] **Step 3: Update docs with the new behavior**

```markdown
<!-- docs/analyzer.md -->
### Committee Flow

* Every ticker receives role-based committee analysis after baseline analyzer output exists
* Growth, Value Skeptic, Risk, Macro, and PM run as independent calls
* Risk, Macro, and PM may rerun with `deep` when PM confidence is low or objections are strong
```

```markdown
<!-- docs/output.md -->
Per-ticker payloads now include:
* `committee_analysis` — always-visible role debate plus PM conclusion
```

```markdown
<!-- docs/cost.md -->
Committee policy:
* default role calls use `economy`
* only escalated `risk_manager`, `macro_strategist`, and `pm` rerun with `deep`
```

- [ ] **Step 4: Run the final targeted regression set**

Run: `python -m unittest tests.test_committee tests.test_committee_output tests.test_model_config tests.test_pipeline_quality_wiring tests.test_output tests.test_output_schema -v`
Expected: PASS for committee-specific coverage and no new output or pipeline regressions

- [ ] **Step 5: Commit**

```bash
git add docs/analyzer.md docs/output.md docs/cost.md tests/test_output_schema.py tests/test_pipeline.py
git commit -m "docs: document committee analysis flow and outputs"
```

---

## Self-Review

### Spec Coverage

- Independent role calls for every ticker: covered by Task 3 and Task 4
- Selective `deep` rerun for `Risk Manager`, `Macro Strategist`, and `PM`: covered by Task 3
- Always-visible default output: covered by Task 5
- Rule-based decision remains official source of truth: preserved by Task 4 and regression checks in Task 6
- Configurable thresholds and model routing: covered by Task 2
- Cost and schema stability: covered by Task 2, Task 5, and Task 6

### Placeholder Scan

- No `TODO` or `TBD` markers remain
- Each code-changing task includes concrete code blocks
- Each verification step includes exact commands

### Type Consistency

- `committee_analysis` is consistently named across `TickerAnalysis`, pipeline wiring, JSON serialization, and Markdown rendering
- Role names are consistently `growth_analyst`, `value_skeptic`, `risk_manager`, `macro_strategist`, and `pm`
- Committee stance mapping uses the same five-level scale everywhere
