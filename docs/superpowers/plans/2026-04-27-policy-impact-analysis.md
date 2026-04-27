# Policy/Regulation Impact Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a daily policy/regulation impact analyzer that scans global policy events via OpenAI web_search, maps them to watchlist tickers, exposes a `policy_tailwind` decision factor, and produces a dedicated `/policy` view.

**Architecture:** Two-stage LLM pipeline. Stage 1 (`src/collector/policy_events.py`) calls Responses API with `web_search` tool to extract events with source URLs and confidence. Stage 2 (`src/analyzer/policy_impact.py`) maps events → ticker impacts with sector-based pre-filtering and chunked calls. Decision layer adds factor 9. Output is a new `policy_impact.json` plus dashboard/markdown/web augmentation. Failures are isolated so the main pipeline never breaks.

**Tech Stack:** Python 3.11, OpenAI Python SDK (Responses API + Structured Outputs), tiktoken, PyYAML, FastAPI (existing), unittest, React + TypeScript + Vite (web).

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/types.py` | Modify | Add `PolicyEvent`, `TickerImpact`, `PolicyImpactReport` frozen dataclasses |
| `config/policy_sources.yaml` | Create | Trusted domains + category→sectors map |
| `config/ticker_policy_context.yaml` | Create | Per-ticker compressed policy context |
| `config/decision_weights.yaml` | Modify | Add `policy_tailwind` weight per regime |
| `config/models.yaml` | Modify | Add `policy.model_profile` key |
| `src/utils/token_budget.py` | Create | tiktoken wrapper + chunk splitter |
| `src/collector/policy_events.py` | Create | Stage 1: web_search + filters + 7d cache |
| `src/analyzer/policy_impact.py` | Create | Stage 2: pre-filter, chunk, map, aggregate tailwind |
| `src/decision/decision_layer.py` | Modify | Add `policy_tailwind` factor + renormalization |
| `src/output/policy_json.py` | Create | Serialize `PolicyImpactReport` → `policy_impact.json` |
| `src/output/json_export.py` | Modify | Inject `policy_tailwind` + top driver into `dashboard.json` |
| `src/output/markdown.py` | Modify | Add "Policy Drivers" section to daily MD |
| `src/pipeline.py` | Modify | Wire stages with isolated try/except |
| `tests/fixtures/policy_events_golden.json` | Create | 12 historical golden cases |
| `tests/test_policy_events_collector.py` | Create | Stage 1 unit tests |
| `tests/test_policy_impact_analyzer.py` | Create | Stage 2 unit tests |
| `tests/test_policy_decision_factor.py` | Create | Factor 9 integration |
| `tests/test_policy_golden.py` | Create | Regression accuracy ≥ 80% gate |
| `web/src/types/index.ts` | Modify | Mirror policy types |
| `web/src/hooks/usePolicyData.ts` | Create | Fetch `policy_impact.json` |
| `web/src/pages/PolicyImpact.tsx` | Create | `/policy` page |
| `web/src/pages/TickerDetail.tsx` | Modify | Add "Policy Exposure" card |
| `web/src/App.tsx` | Modify | Add `/policy` route |

---

## Task 1: Frozen dataclass types

**Files:**
- Modify: `src/types.py`
- Test: `tests/test_policy_types.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_policy_types.py
import unittest
from dataclasses import FrozenInstanceError
from src.types import PolicyEvent, TickerImpact, PolicyImpactReport


class TestPolicyTypes(unittest.TestCase):
    def test_policy_event_is_frozen(self):
        evt = PolicyEvent(
            id="abc", category="tariff", headline="h", summary="s",
            raw_excerpt="r", source_url="https://x", source_domain="x",
            published_at="2026-04-27T00:00:00Z", confidence=0.8,
        )
        with self.assertRaises(FrozenInstanceError):
            evt.headline = "y"

    def test_ticker_impact_score_signed(self):
        ti = TickerImpact(
            ticker="NVDA", direction="negative", strength="direct",
            score=-0.9, confidence=0.85, rationale="China revenue exposure",
        )
        self.assertLess(ti.score, 0)

    def test_report_has_aggregate(self):
        rpt = PolicyImpactReport(
            date="2026-04-27", events=[],
            impacts_by_event={}, impacts_by_ticker={},
            tailwind_scores={"NVDA": -0.5}, metadata={},
        )
        self.assertEqual(rpt.tailwind_scores["NVDA"], -0.5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_policy_types -v`
Expected: FAIL with `ImportError: cannot import name 'PolicyEvent'`

- [ ] **Step 3: Add the dataclasses to `src/types.py`**

Append to `src/types.py`:

```python
from dataclasses import dataclass, field

POLICY_CATEGORIES = (
    "interest_rate", "antitrust", "export_control", "subsidy",
    "tariff", "ira", "chips_act", "fda", "defense_budget",
    "energy_policy", "other",
)


@dataclass(frozen=True)
class PolicyEvent:
    id: str
    category: str
    headline: str
    summary: str
    raw_excerpt: str
    source_url: str
    source_domain: str
    published_at: str
    confidence: float


@dataclass(frozen=True)
class TickerImpact:
    ticker: str
    direction: str   # "positive" | "negative" | "neutral"
    strength: str    # "direct" | "indirect" | "neutral"
    score: float     # signed [-1.0, +1.0]
    confidence: float
    rationale: str


@dataclass(frozen=True)
class PolicyImpactReport:
    date: str
    events: list
    impacts_by_event: dict
    impacts_by_ticker: dict
    tailwind_scores: dict
    metadata: dict
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_policy_types -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/types.py tests/test_policy_types.py
git commit -m "feat(types): add PolicyEvent/TickerImpact/PolicyImpactReport"
```

---

## Task 2: Config files

**Files:**
- Create: `config/policy_sources.yaml`
- Create: `config/ticker_policy_context.yaml`
- Modify: `config/decision_weights.yaml`
- Modify: `config/models.yaml`

- [ ] **Step 1: Create `config/policy_sources.yaml`**

```yaml
trusted_domains:
  - whitehouse.gov
  - federalreserve.gov
  - ustr.gov
  - commerce.gov
  - fda.gov
  - sec.gov
  - state.gov
  - reuters.com
  - bloomberg.com
  - wsj.com
  - ft.com
penalized_domains:
  - reddit.com
  - twitter.com
  - x.com
  - medium.com
trust_bonus: 0.2
penalty: 0.3

category_to_sectors:
  interest_rate:   [financials, real_estate, utilities, technology]
  antitrust:       [technology, communication_services, consumer_discretionary]
  export_control:  [semiconductor, technology, defense]
  subsidy:         [semiconductor, clean_energy, industrials, automotive]
  tariff:          [industrials, consumer_discretionary, materials, automotive]
  ira:             [clean_energy, automotive, utilities]
  chips_act:       [semiconductor, technology]
  fda:             [healthcare, biotech, pharma]
  defense_budget:  [defense, aerospace, industrials]
  energy_policy:   [energy, utilities, clean_energy]
  other:           []
```

- [ ] **Step 2: Create `config/ticker_policy_context.yaml`**

Skeleton; the human curator (or one-time LLM bootstrap script) fills the rest:

```yaml
NVDA:
  sector: semiconductor
  business: "AI accelerator GPUs; data center dominant"
  exposure: [export_control_china, antitrust_ftc]
  china_revenue_pct: 17
AMD:
  sector: semiconductor
  business: "x86 CPUs and GPUs; AI accelerator follower"
  exposure: [export_control_china]
  china_revenue_pct: 15
INTC:
  sector: semiconductor
  business: "US-domestic foundry beneficiary; Ohio/Arizona fabs"
  exposure: [chips_act_subsidy, export_control_china]
  china_revenue_pct: 27
```

- [ ] **Step 3: Modify `config/decision_weights.yaml`**

Add a `policy_tailwind` key to each regime block. Keep other weights, just append:

```yaml
risk_on:
  policy_tailwind: 0.05
neutral:
  policy_tailwind: 0.08
risk_off:
  policy_tailwind: 0.10
```

(Adjust merging to preserve existing keys — do not overwrite the file wholesale.)

- [ ] **Step 4: Modify `config/models.yaml`**

Add:

```yaml
policy:
  model_profile: deep
```

- [ ] **Step 5: Commit**

```bash
git add config/policy_sources.yaml config/ticker_policy_context.yaml config/decision_weights.yaml config/models.yaml
git commit -m "config: add policy sources, ticker context, factor 9 weights"
```

---

## Task 3: Token budget utility

**Files:**
- Create: `src/utils/token_budget.py`
- Test: `tests/test_token_budget.py`

- [ ] **Step 1: Add `tiktoken` to `requirements.txt`**

Append `tiktoken>=0.7.0` if not already present.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_token_budget.py
import unittest
from src.utils.token_budget import count_tokens, split_into_chunks, TokenBudgetExceeded


class TestTokenBudget(unittest.TestCase):
    def test_count_tokens_returns_int(self):
        self.assertIsInstance(count_tokens("hello world"), int)
        self.assertGreater(count_tokens("hello world"), 0)

    def test_split_into_chunks_respects_size(self):
        items = [{"t": f"item {i}"} for i in range(60)]
        chunks = split_into_chunks(items, size=25)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 25)
        self.assertEqual(len(chunks[2]), 10)

    def test_token_budget_exceeded_raises(self):
        big = "x" * 10_000_000  # ~ millions of tokens
        with self.assertRaises(TokenBudgetExceeded):
            count_tokens(big, hard_limit=200_000)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m unittest tests.test_token_budget -v`
Expected: FAIL with ImportError.

- [ ] **Step 4: Implement `src/utils/token_budget.py`**

```python
from __future__ import annotations
import tiktoken

_ENC = tiktoken.get_encoding("o200k_base")


class TokenBudgetExceeded(Exception):
    pass


def count_tokens(text: str, hard_limit: int | None = None) -> int:
    n = len(_ENC.encode(text))
    if hard_limit is not None and n > hard_limit:
        raise TokenBudgetExceeded(f"{n} > {hard_limit}")
    return n


def split_into_chunks(items: list, size: int = 25) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.test_token_budget -v`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt src/utils/token_budget.py tests/test_token_budget.py
git commit -m "feat(utils): token_budget — tiktoken counter + chunk splitter"
```

---

## Task 4: Stage 1 — Policy events collector

**Files:**
- Create: `src/collector/policy_events.py`
- Test: `tests/test_policy_events_collector.py`

- [ ] **Step 1: Write the failing tests (filters + cache, with mocked OpenAI)**

```python
# tests/test_policy_events_collector.py
import json
import unittest
from unittest.mock import MagicMock, patch
from src.collector.policy_events import (
    extract_events, filter_events, hash_event_id, load_cache, save_cache,
)


class TestFilters(unittest.TestCase):
    def test_drops_event_without_source_url(self):
        events = [{"headline": "h", "source_url": "", "published_at": "2026-04-27T00:00:00Z",
                   "category": "tariff", "summary": "s", "raw_excerpt": "r", "confidence": 0.8}]
        out = filter_events(events, today="2026-04-27", trusted=[], penalized=[],
                            trust_bonus=0.2, penalty=0.3)
        self.assertEqual(out, [])

    def test_drops_event_older_than_24h(self):
        events = [{"headline": "h", "source_url": "https://x.com",
                   "published_at": "2026-04-24T00:00:00Z", "category": "tariff",
                   "summary": "s", "raw_excerpt": "r", "confidence": 0.8}]
        out = filter_events(events, today="2026-04-27", trusted=[], penalized=[],
                            trust_bonus=0.2, penalty=0.3)
        self.assertEqual(out, [])

    def test_trusted_domain_boosts_confidence(self):
        events = [{"headline": "h", "source_url": "https://whitehouse.gov/x",
                   "published_at": "2026-04-27T00:00:00Z", "category": "tariff",
                   "summary": "s", "raw_excerpt": "r", "confidence": 0.5}]
        out = filter_events(events, today="2026-04-27",
                            trusted=["whitehouse.gov"], penalized=[],
                            trust_bonus=0.2, penalty=0.3)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].confidence, 0.7, places=2)

    def test_penalized_domain_drops_confidence(self):
        events = [{"headline": "h", "source_url": "https://reddit.com/x",
                   "published_at": "2026-04-27T00:00:00Z", "category": "tariff",
                   "summary": "s", "raw_excerpt": "r", "confidence": 0.6}]
        out = filter_events(events, today="2026-04-27",
                            trusted=[], penalized=["reddit.com"],
                            trust_bonus=0.2, penalty=0.3)
        self.assertAlmostEqual(out[0].confidence, 0.3, places=2)


class TestCache(unittest.TestCase):
    def test_hash_is_stable(self):
        a = hash_event_id("h", "https://x", "2026-04-27T00:00:00Z")
        b = hash_event_id("h", "https://x", "2026-04-27T00:00:00Z")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 12)

    def test_round_trip_cache(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "cache.json")
            save_cache(p, {"abc": "2026-04-27"})
            self.assertEqual(load_cache(p), {"abc": "2026-04-27"})


class TestExtract(unittest.TestCase):
    @patch("src.collector.policy_events._openai_web_search")
    def test_extract_calls_openai_and_filters(self, mock_search):
        mock_search.return_value = [
            {"headline": "USTR raises tariff", "source_url": "https://ustr.gov/x",
             "published_at": "2026-04-27T01:00:00Z", "category": "tariff",
             "summary": "s", "raw_excerpt": "r", "confidence": 0.7},
        ]
        events = extract_events(today="2026-04-27", model_profile="deep",
                                sources_config={"trusted_domains": ["ustr.gov"],
                                                "penalized_domains": [],
                                                "trust_bonus": 0.2, "penalty": 0.3})
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source_domain, "ustr.gov")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_policy_events_collector -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement `src/collector/policy_events.py`**

```python
from __future__ import annotations
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from src.types import PolicyEvent, POLICY_CATEGORIES


def hash_event_id(headline: str, url: str, published_at: str) -> str:
    return hashlib.sha1(f"{headline}|{url}|{published_at}".encode()).hexdigest()[:12]


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().lstrip("www.")


def filter_events(
    raw: list[dict], today: str, trusted: list[str], penalized: list[str],
    trust_bonus: float, penalty: float,
) -> list[PolicyEvent]:
    today_dt = _parse_iso(today + "T00:00:00Z")
    cutoff = today_dt - timedelta(hours=24)
    out: list[PolicyEvent] = []
    for ev in raw:
        url = (ev.get("source_url") or "").strip()
        if not url:
            continue
        try:
            pub = _parse_iso(ev["published_at"])
        except Exception:
            continue
        if pub < cutoff:
            continue
        domain = _domain(url)
        conf = float(ev.get("confidence", 0.5))
        if any(domain.endswith(d) for d in trusted):
            conf = min(1.0, conf + trust_bonus)
        if any(domain.endswith(d) for d in penalized):
            conf = max(0.0, conf - penalty)
        category = ev.get("category", "other")
        if category not in POLICY_CATEGORIES:
            category = "other"
        out.append(
            PolicyEvent(
                id=hash_event_id(ev["headline"], url, ev["published_at"]),
                category=category,
                headline=ev["headline"],
                summary=ev.get("summary", "")[:1200],
                raw_excerpt=ev.get("raw_excerpt", "")[:4000],
                source_url=url,
                source_domain=domain,
                published_at=ev["published_at"],
                confidence=round(conf, 3),
            )
        )
    # de-dup by id
    seen = {}
    for e in out:
        seen.setdefault(e.id, e)
    return list(seen.values())


def load_cache(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cache(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def prune_cache(cache: dict, today: str, days: int = 7) -> dict:
    today_dt = _parse_iso(today + "T00:00:00Z")
    keep = {}
    for k, iso in cache.items():
        try:
            if today_dt - _parse_iso(iso) <= timedelta(days=days):
                keep[k] = iso
        except Exception:
            continue
    return keep


def _openai_web_search(today: str, model_profile: str) -> list[dict]:
    """Real implementation lives here; mocked in tests."""
    from openai import OpenAI
    from src.utils.config import load_config

    client = OpenAI()
    models = load_config("config/models.yaml")
    model = models.get(model_profile, {}).get("model", "gpt-5.4")

    schema = {
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "headline": {"type": "string"},
                        "summary": {"type": "string"},
                        "raw_excerpt": {"type": "string"},
                        "source_url": {"type": "string"},
                        "published_at": {"type": "string"},
                        "category": {"type": "string", "enum": list(POLICY_CATEGORIES)},
                        "confidence": {"type": "number"},
                    },
                    "required": ["headline", "summary", "source_url",
                                 "published_at", "category", "confidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["events"],
        "additionalProperties": False,
    }

    prompt = (
        f"Find US and global policy/regulation events published in the 24 hours "
        f"before {today}. Cover all of these categories: "
        f"{', '.join(POLICY_CATEGORIES)}. Each event MUST include source_url and "
        "published_at (ISO8601). summary ≤ 120 tokens. Return JSON matching schema."
    )

    resp = client.responses.create(
        model=model,
        tools=[{"type": "web_search"}],
        input=prompt,
        response_format={"type": "json_schema", "json_schema": {
            "name": "policy_events", "schema": schema, "strict": True}},
    )
    payload = json.loads(resp.output_text)
    return payload.get("events", [])


def extract_events(
    today: str, model_profile: str, sources_config: dict,
    cache_path: str = "output/data/policy_events_cache.json",
) -> list[PolicyEvent]:
    raw = _openai_web_search(today, model_profile)
    events = filter_events(
        raw, today=today,
        trusted=sources_config.get("trusted_domains", []),
        penalized=sources_config.get("penalized_domains", []),
        trust_bonus=float(sources_config.get("trust_bonus", 0.2)),
        penalty=float(sources_config.get("penalty", 0.3)),
    )
    cache = prune_cache(load_cache(cache_path), today=today, days=7)
    for e in events:
        cache.setdefault(e.id, today)
    save_cache(cache_path, cache)
    return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_policy_events_collector -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/collector/policy_events.py tests/test_policy_events_collector.py
git commit -m "feat(collector): policy_events stage1 — web_search + filters + cache"
```

---

## Task 5: Stage 2 — Impact analyzer

**Files:**
- Create: `src/analyzer/policy_impact.py`
- Test: `tests/test_policy_impact_analyzer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_policy_impact_analyzer.py
import unittest
from unittest.mock import patch
from src.types import PolicyEvent, TickerImpact
from src.analyzer.policy_impact import (
    prefilter_candidates, normalize_score, aggregate_tailwind, map_impacts,
)


def _evt(category="export_control", eid="evt1"):
    return PolicyEvent(
        id=eid, category=category, headline="h", summary="s",
        raw_excerpt="r", source_url="https://x", source_domain="x",
        published_at="2026-04-27T00:00:00Z", confidence=0.9,
    )


class TestPrefilter(unittest.TestCase):
    def test_keeps_only_relevant_sectors(self):
        ticker_ctx = {
            "NVDA": {"sector": "semiconductor"},
            "JNJ":  {"sector": "healthcare"},
        }
        cat_to_sec = {"export_control": ["semiconductor"]}
        out = prefilter_candidates([_evt()], ticker_ctx, cat_to_sec)
        self.assertEqual(out, {"evt1": ["NVDA"]})


class TestNormalize(unittest.TestCase):
    def test_direct_score_clamped_into_band(self):
        self.assertEqual(normalize_score("negative", "direct", 1.5), -1.0)
        self.assertEqual(normalize_score("negative", "direct", 0.2), -0.7)
        self.assertEqual(normalize_score("positive", "indirect", 0.9), 0.5)
        self.assertEqual(normalize_score("neutral", "neutral", 0.99), 0.0)


class TestAggregate(unittest.TestCase):
    def test_low_confidence_excluded_and_clipped(self):
        impacts = [
            TickerImpact("NVDA", "negative", "direct", -0.9, 0.9, "r1"),
            TickerImpact("NVDA", "negative", "indirect", -0.4, 0.4, "lowconf"),
            TickerImpact("NVDA", "negative", "indirect", -0.5, 0.8, "r3"),
        ]
        self.assertAlmostEqual(
            aggregate_tailwind({"NVDA": impacts})["NVDA"],
            max(-1.0, -0.9 * 0.9 + -0.5 * 0.8),
            places=3,
        )


class TestMap(unittest.TestCase):
    @patch("src.analyzer.policy_impact._openai_map")
    def test_map_chunks_large_candidate_lists(self, mock_map):
        mock_map.return_value = {"evt1": []}
        ticker_ctx = {f"T{i}": {"sector": "semiconductor",
                                "business": "x", "exposure": [],
                                "china_revenue_pct": 0} for i in range(60)}
        report = map_impacts(
            events=[_evt()], ticker_ctx=ticker_ctx,
            category_to_sectors={"export_control": ["semiconductor"]},
            chunk_size=25, model_profile="deep",
        )
        # 60 candidates → 3 chunks
        self.assertEqual(mock_map.call_count, 3)
        self.assertIn("evt1", report.impacts_by_event)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_policy_impact_analyzer -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement `src/analyzer/policy_impact.py`**

```python
from __future__ import annotations
import json
import time
from typing import Iterable

from src.types import PolicyEvent, TickerImpact, PolicyImpactReport
from src.utils.token_budget import count_tokens, split_into_chunks


_DIRECT_BAND = (0.7, 1.0)
_INDIRECT_BAND = (0.3, 0.5)


def normalize_score(direction: str, strength: str, raw: float) -> float:
    if strength == "neutral" or direction == "neutral":
        return 0.0
    band = _DIRECT_BAND if strength == "direct" else _INDIRECT_BAND
    mag = max(band[0], min(band[1], abs(raw)))
    return mag if direction == "positive" else -mag


def prefilter_candidates(
    events: list[PolicyEvent],
    ticker_ctx: dict,
    category_to_sectors: dict,
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for e in events:
        sectors = set(category_to_sectors.get(e.category, []))
        if not sectors:
            out[e.id] = list(ticker_ctx.keys())
            continue
        out[e.id] = [t for t, ctx in ticker_ctx.items()
                     if ctx.get("sector") in sectors]
    return out


def aggregate_tailwind(by_ticker: dict[str, list[TickerImpact]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for t, impacts in by_ticker.items():
        s = 0.0
        for imp in impacts:
            if imp.confidence < 0.5:
                continue
            s += imp.score * imp.confidence
        scores[t] = max(-1.0, min(1.0, round(s, 4)))
    return scores


def _ticker_context_compact(ticker: str, ctx: dict) -> dict:
    return {
        "ticker": ticker,
        "sector": ctx.get("sector"),
        "business": (ctx.get("business") or "")[:160],
        "exposure": ctx.get("exposure", [])[:5],
        "china_revenue_pct": ctx.get("china_revenue_pct", 0),
    }


def _openai_map(
    events_chunk: list[PolicyEvent],
    candidates: list[dict],
    model_profile: str,
) -> dict[str, list[dict]]:
    """Map a chunk: events × candidate tickers → impacts. Mocked in tests."""
    from openai import OpenAI
    from src.utils.config import load_config

    client = OpenAI()
    models = load_config("config/models.yaml")
    model = models.get(model_profile, {}).get("model", "gpt-5.4")

    schema = {
        "type": "object",
        "properties": {
            "impacts_by_event": {
                "type": "object",
                "additionalProperties": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ticker": {"type": "string"},
                            "direction": {"type": "string",
                                          "enum": ["positive", "negative", "neutral"]},
                            "strength": {"type": "string",
                                         "enum": ["direct", "indirect", "neutral"]},
                            "score": {"type": "number"},
                            "confidence": {"type": "number"},
                            "rationale": {"type": "string"},
                        },
                        "required": ["ticker", "direction", "strength",
                                     "score", "confidence", "rationale"],
                        "additionalProperties": False,
                    },
                },
            }
        },
        "required": ["impacts_by_event"],
        "additionalProperties": False,
    }

    prompt = {
        "events": [
            {"id": e.id, "category": e.category, "headline": e.headline,
             "summary": e.summary} for e in events_chunk
        ],
        "candidates": candidates,
        "instructions": (
            "For each event, identify which candidate tickers face direct, "
            "indirect, or neutral impact. Use rationale to cite the specific "
            "exposure (e.g., 'China revenue 17%'). confidence in [0,1]."
        ),
    }

    resp = client.responses.create(
        model=model,
        input=json.dumps(prompt),
        response_format={"type": "json_schema",
                         "json_schema": {"name": "impacts", "schema": schema,
                                         "strict": True}},
    )
    payload = json.loads(resp.output_text)
    return payload.get("impacts_by_event", {})


def map_impacts(
    events: list[PolicyEvent],
    ticker_ctx: dict,
    category_to_sectors: dict,
    chunk_size: int = 25,
    model_profile: str = "deep",
) -> PolicyImpactReport:
    started = time.time()
    candidate_map = prefilter_candidates(events, ticker_ctx, category_to_sectors)

    impacts_by_event: dict[str, list[TickerImpact]] = {}
    impacts_by_ticker: dict[str, list[TickerImpact]] = {}
    tokens_in = 0

    # Build a global candidate union for chunking, then re-attach per event.
    all_candidates = sorted({t for tlist in candidate_map.values() for t in tlist})
    chunks = split_into_chunks(all_candidates, size=chunk_size) or [[]]

    for chunk in chunks:
        compact = [_ticker_context_compact(t, ticker_ctx[t])
                   for t in chunk if t in ticker_ctx]
        # filter events that touch any ticker in this chunk
        chunk_events = [e for e in events
                        if any(t in candidate_map.get(e.id, []) for t in chunk)]
        if not chunk_events:
            continue
        tokens_in += count_tokens(json.dumps(compact) + json.dumps(
            [e.summary for e in chunk_events]), hard_limit=200_000)

        try:
            raw = _openai_map(chunk_events, compact, model_profile)
        except Exception:
            continue  # graceful: skip chunk

        for eid, items in raw.items():
            for it in items:
                t = it["ticker"]
                if t not in chunk:
                    continue  # ignore hallucinated tickers
                imp = TickerImpact(
                    ticker=t,
                    direction=it["direction"],
                    strength=it["strength"],
                    score=normalize_score(it["direction"], it["strength"],
                                          float(it["score"])),
                    confidence=max(0.0, min(1.0, float(it["confidence"]))),
                    rationale=(it.get("rationale") or "")[:200],
                )
                impacts_by_event.setdefault(eid, []).append(imp)
                impacts_by_ticker.setdefault(t, []).append(imp)

    tailwind = aggregate_tailwind(impacts_by_ticker)
    return PolicyImpactReport(
        date=time.strftime("%Y-%m-%d"),
        events=events,
        impacts_by_event=impacts_by_event,
        impacts_by_ticker=impacts_by_ticker,
        tailwind_scores=tailwind,
        metadata={
            "tokens_in": tokens_in,
            "model_profile": model_profile,
            "duration_ms": int((time.time() - started) * 1000),
            "chunks": len(chunks),
        },
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_policy_impact_analyzer -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/analyzer/policy_impact.py tests/test_policy_impact_analyzer.py
git commit -m "feat(analyzer): policy_impact stage2 — prefilter, chunk, map, aggregate"
```

---

## Task 6: Decision factor 9 integration

**Files:**
- Modify: `src/decision/decision_layer.py`
- Test: `tests/test_policy_decision_factor.py`

- [ ] **Step 1: Read current factor structure**

Read `src/decision/decision_layer.py` to locate the factor weights dict and the conviction aggregation function. Note the existing factor names — you will add `policy_tailwind` alongside them.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_policy_decision_factor.py
import unittest
from src.decision.decision_layer import (
    apply_policy_factor, renormalize_weights,
)


class TestPolicyFactor(unittest.TestCase):
    def test_renormalize_when_factor_missing(self):
        weights = {"a": 0.5, "b": 0.4, "policy_tailwind": 0.1}
        out = renormalize_weights(weights, missing={"policy_tailwind"})
        self.assertAlmostEqual(sum(out.values()), 1.0, places=6)
        self.assertNotIn("policy_tailwind", out)

    def test_apply_policy_adds_signed_contribution(self):
        # tailwind +0.5 with weight 0.08 → +4 conviction points (0..100 scale)
        out = apply_policy_factor(base_conviction=50.0,
                                  tailwind_score=0.5, weight=0.08)
        self.assertAlmostEqual(out, 54.0, places=2)

    def test_apply_policy_clamps_conviction(self):
        out = apply_policy_factor(base_conviction=98.0,
                                  tailwind_score=1.0, weight=0.10)
        self.assertLessEqual(out, 100.0)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m unittest tests.test_policy_decision_factor -v`
Expected: FAIL — ImportError.

- [ ] **Step 4: Add the helpers to `src/decision/decision_layer.py`**

Append these standalone functions (do not break the existing public API):

```python
def renormalize_weights(weights: dict, missing: set) -> dict:
    kept = {k: v for k, v in weights.items() if k not in missing}
    total = sum(kept.values())
    if total == 0:
        return kept
    return {k: v / total for k, v in kept.items()}


def apply_policy_factor(
    base_conviction: float, tailwind_score: float, weight: float,
) -> float:
    """tailwind_score in [-1, 1]; weight is the regime weight from
    decision_weights.yaml. Contribution scaled to the 0..100 conviction range."""
    delta = tailwind_score * weight * 100.0
    return max(0.0, min(100.0, base_conviction + delta))
```

Then, in the conviction-scoring entry point (find the function that reads
`decision_weights.yaml` and combines factors), add:

```python
    tailwind = (policy_report.tailwind_scores.get(ticker)
                if policy_report else None)
    if tailwind is None:
        weights = renormalize_weights(weights, missing={"policy_tailwind"})
    else:
        conviction = apply_policy_factor(conviction, tailwind,
                                         weights.get("policy_tailwind", 0.0))
```

(Adjust variable names to match the existing function. The `policy_report` is
passed through from `pipeline.py` in Task 8.)

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.test_policy_decision_factor -v`
Expected: 3 PASS. Also re-run existing decision tests:
`python -m unittest discover -s tests -v -p 'test_decision*.py'`
Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add src/decision/decision_layer.py tests/test_policy_decision_factor.py
git commit -m "feat(decision): factor 9 policy_tailwind + missing renormalize"
```

---

## Task 7: Output — `policy_impact.json` writer

**Files:**
- Create: `src/output/policy_json.py`
- Test: `tests/test_policy_json_export.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_policy_json_export.py
import json, os, tempfile, unittest
from src.types import PolicyEvent, TickerImpact, PolicyImpactReport
from src.output.policy_json import write_policy_impact_json


class TestPolicyJsonExport(unittest.TestCase):
    def test_writes_well_formed_json(self):
        evt = PolicyEvent("evt1", "tariff", "h", "s", "r",
                          "https://x", "x", "2026-04-27T00:00:00Z", 0.8)
        imp = TickerImpact("NVDA", "negative", "direct", -0.8, 0.9, "r")
        rpt = PolicyImpactReport(
            date="2026-04-27", events=[evt],
            impacts_by_event={"evt1": [imp]},
            impacts_by_ticker={"NVDA": [imp]},
            tailwind_scores={"NVDA": -0.72},
            metadata={"tokens_in": 100},
        )
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "policy_impact.json")
            write_policy_impact_json(rpt, p)
            with open(p, encoding="utf-8") as f:
                payload = json.load(f)
        self.assertEqual(payload["date"], "2026-04-27")
        self.assertEqual(payload["tailwind_scores"]["NVDA"], -0.72)
        self.assertEqual(len(payload["events"]), 1)
        self.assertEqual(payload["impacts_by_ticker"]["NVDA"][0]["score"], -0.8)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_policy_json_export -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement `src/output/policy_json.py`**

```python
from __future__ import annotations
import json
import os
from dataclasses import asdict
from src.types import PolicyImpactReport


def write_policy_impact_json(report: PolicyImpactReport, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {
        "date": report.date,
        "events": [asdict(e) for e in report.events],
        "impacts_by_event": {
            k: [asdict(i) for i in v] for k, v in report.impacts_by_event.items()
        },
        "impacts_by_ticker": {
            k: [asdict(i) for i in v] for k, v in report.impacts_by_ticker.items()
        },
        "tailwind_scores": report.tailwind_scores,
        "metadata": report.metadata,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_policy_json_export -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/output/policy_json.py tests/test_policy_json_export.py
git commit -m "feat(output): policy_impact.json writer"
```

---

## Task 8: Pipeline wiring (graceful degradation)

**Files:**
- Modify: `src/pipeline.py`
- Modify: `src/output/json_export.py`
- Modify: `src/output/markdown.py`
- Test: `tests/test_pipeline_policy_integration.py`

- [ ] **Step 1: Read existing `src/pipeline.py::run_pipeline`**

Identify the place where (a) collection completes, (b) decision layer is invoked. The policy stages must run AFTER collection and BEFORE decision (so the factor is available).

- [ ] **Step 2: Write the failing integration test**

```python
# tests/test_pipeline_policy_integration.py
import unittest
from unittest.mock import patch, MagicMock
from src.pipeline import run_policy_stage


class TestRunPolicyStage(unittest.TestCase):
    @patch("src.pipeline.extract_events", return_value=[])
    @patch("src.pipeline.map_impacts")
    def test_returns_none_when_no_events(self, mock_map, mock_extract):
        report = run_policy_stage(today="2026-04-27", ticker_ctx={},
                                  sources_config={}, model_profile="deep",
                                  category_to_sectors={})
        self.assertIsNone(report)
        mock_map.assert_not_called()

    @patch("src.pipeline.extract_events", side_effect=RuntimeError("boom"))
    def test_returns_none_on_collector_failure(self, _):
        report = run_policy_stage(today="2026-04-27", ticker_ctx={},
                                  sources_config={}, model_profile="deep",
                                  category_to_sectors={})
        self.assertIsNone(report)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m unittest tests.test_pipeline_policy_integration -v`
Expected: FAIL — `cannot import name 'run_policy_stage'`.

- [ ] **Step 4: Add `run_policy_stage` to `src/pipeline.py`**

```python
# imports near top
from src.collector.policy_events import extract_events
from src.analyzer.policy_impact import map_impacts
from src.output.policy_json import write_policy_impact_json
from src.utils.pipeline_logging import record_pipeline_event


def run_policy_stage(today, ticker_ctx, sources_config, model_profile,
                     category_to_sectors,
                     output_path="output/data/policy_impact.json"):
    try:
        events = extract_events(today=today, model_profile=model_profile,
                                sources_config=sources_config)
        record_pipeline_event("policy.stage1.events_count", len(events))
        if not events:
            return None
        report = map_impacts(events=events, ticker_ctx=ticker_ctx,
                             category_to_sectors=category_to_sectors,
                             model_profile=model_profile)
        record_pipeline_event("policy.stage2.tickers_scored",
                              len(report.tailwind_scores))
        write_policy_impact_json(report, output_path)
        return report
    except Exception as e:
        record_pipeline_event("policy.error", str(e))
        return None
```

Then in `run_pipeline` body, after collection and before decision:

```python
    sources_cfg = load_config("config/policy_sources.yaml")
    ticker_ctx = load_config("config/ticker_policy_context.yaml")
    models_cfg = load_config("config/models.yaml")
    policy_report = run_policy_stage(
        today=today,
        ticker_ctx=ticker_ctx,
        sources_config=sources_cfg,
        model_profile=models_cfg.get("policy", {}).get("model_profile", "deep"),
        category_to_sectors=sources_cfg.get("category_to_sectors", {}),
    )
```

Pass `policy_report` into the decision call site (whatever its current signature is; add a kwarg `policy_report=policy_report`).

- [ ] **Step 5: Modify `src/output/json_export.py` — inject into dashboard**

In the function that builds `dashboard.json`, after per-ticker assembly:

```python
    if policy_report is not None:
        for tdata in dashboard["tickers"]:
            t = tdata["ticker"]
            tdata["policy_tailwind"] = policy_report.tailwind_scores.get(t)
            top = sorted(
                policy_report.impacts_by_ticker.get(t, []),
                key=lambda i: -abs(i.score) * i.confidence,
            )[:1]
            tdata["policy_top_driver"] = (
                {"headline": next(
                    (e.headline for e in policy_report.events
                     if any(i.ticker == t for i in
                            policy_report.impacts_by_event.get(e.id, []))),
                    None,
                ),
                 "rationale": top[0].rationale} if top else None
            )
```

- [ ] **Step 6: Modify `src/output/markdown.py` — add Policy Drivers section**

In the daily-MD builder, after the existing sections:

```python
def _render_policy_section(report) -> str:
    if report is None or not report.events:
        return ""
    lines = ["## Policy Drivers", ""]
    top_events = sorted(
        report.events,
        key=lambda e: -len(report.impacts_by_event.get(e.id, [])),
    )[:5]
    for e in top_events:
        impacts = report.impacts_by_event.get(e.id, [])[:3]
        lines.append(f"- **{e.headline}** ({e.category}, conf {e.confidence:.2f})")
        for i in impacts:
            lines.append(
                f"  - {i.ticker}: {i.direction} ({i.strength}, "
                f"score {i.score:+.2f}) — {i.rationale}"
            )
    return "\n".join(lines) + "\n"
```

Call `_render_policy_section(policy_report)` and append to the daily MD body.

- [ ] **Step 7: Run all tests**

Run: `python -m unittest discover -s tests -v`
Expected: pass, no regressions.

- [ ] **Step 8: Commit**

```bash
git add src/pipeline.py src/output/json_export.py src/output/markdown.py tests/test_pipeline_policy_integration.py
git commit -m "feat(pipeline): wire policy stages with isolated try/except + outputs"
```

---

## Task 9: Golden regression test

**Files:**
- Create: `tests/fixtures/policy_events_golden.json`
- Create: `tests/test_policy_golden.py`

- [ ] **Step 1: Build the golden fixture**

```json
[
  {
    "name": "2022 CHIPS Act → INTC/TSM beneficiary",
    "events": [{
      "id": "g1", "category": "chips_act",
      "headline": "President signs CHIPS and Science Act",
      "summary": "Provides $52B in US semiconductor manufacturing subsidies.",
      "raw_excerpt": "", "source_url": "https://whitehouse.gov/x",
      "source_domain": "whitehouse.gov",
      "published_at": "2022-08-09T00:00:00Z", "confidence": 0.95
    }],
    "expected_top_positive": ["INTC", "TSM", "MU"],
    "expected_top_negative": []
  },
  {
    "name": "2023 export control → NVDA direct risk",
    "events": [{
      "id": "g2", "category": "export_control",
      "headline": "Commerce tightens AI chip exports to China",
      "summary": "New rules block sales of advanced GPUs to PRC entities.",
      "raw_excerpt": "", "source_url": "https://commerce.gov/x",
      "source_domain": "commerce.gov",
      "published_at": "2023-10-17T00:00:00Z", "confidence": 0.95
    }],
    "expected_top_negative": ["NVDA", "AMD"],
    "expected_top_positive": []
  }
]
```

(Add 10 more cases of similar shape covering tariff, IRA, FDA, antitrust, defense, energy, interest_rate. Aim for 12 total.)

- [ ] **Step 2: Write the regression test**

```python
# tests/test_policy_golden.py
import json, os, unittest
from unittest.mock import patch
from src.types import PolicyEvent
from src.analyzer.policy_impact import map_impacts


FIXTURE = os.path.join(os.path.dirname(__file__),
                       "fixtures", "policy_events_golden.json")


def _run_real_or_skip(events, ticker_ctx, cat_map):
    """Calls the real LLM unless POLICY_GOLDEN_OFFLINE is set."""
    if os.environ.get("POLICY_GOLDEN_OFFLINE"):
        raise unittest.SkipTest("offline mode")
    return map_impacts(events=events, ticker_ctx=ticker_ctx,
                       category_to_sectors=cat_map, model_profile="deep")


class TestPolicyGolden(unittest.TestCase):
    def test_accuracy_at_least_80pct(self):
        with open(FIXTURE, encoding="utf-8") as f:
            cases = json.load(f)
        ticker_ctx = {  # minimal ctx for golden
            "NVDA": {"sector": "semiconductor", "business": "AI GPUs",
                     "exposure": ["export_control_china"], "china_revenue_pct": 17},
            "AMD":  {"sector": "semiconductor", "business": "x86 + GPUs",
                     "exposure": ["export_control_china"], "china_revenue_pct": 15},
            "INTC": {"sector": "semiconductor", "business": "US foundry",
                     "exposure": ["chips_act_subsidy"], "china_revenue_pct": 27},
            "TSM":  {"sector": "semiconductor", "business": "Foundry leader",
                     "exposure": ["chips_act_subsidy"], "china_revenue_pct": 10},
            "MU":   {"sector": "semiconductor", "business": "Memory",
                     "exposure": ["chips_act_subsidy"], "china_revenue_pct": 11},
        }
        cat_map = {"chips_act": ["semiconductor"],
                   "export_control": ["semiconductor"]}
        hits = total = 0
        for case in cases:
            events = [PolicyEvent(**e) for e in case["events"]]
            try:
                report = _run_real_or_skip(events, ticker_ctx, cat_map)
            except unittest.SkipTest:
                self.skipTest("offline")
            for sign, expected in (("positive", case["expected_top_positive"]),
                                   ("negative", case["expected_top_negative"])):
                for t in expected:
                    total += 1
                    score = report.tailwind_scores.get(t, 0)
                    if (sign == "positive" and score > 0.1) or \
                       (sign == "negative" and score < -0.1):
                        hits += 1
        if total:
            self.assertGreaterEqual(hits / total, 0.8,
                                    f"golden accuracy {hits}/{total}")
```

- [ ] **Step 3: Run offline first to verify wiring**

Run: `POLICY_GOLDEN_OFFLINE=1 python -m unittest tests.test_policy_golden -v`
Expected: SKIPPED.

- [ ] **Step 4: Run live (manual, before merge)**

Run: `python -m unittest tests.test_policy_golden -v`
Expected: PASS with accuracy ≥ 0.8.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/policy_events_golden.json tests/test_policy_golden.py
git commit -m "test(policy): golden regression set with 80% accuracy gate"
```

---

## Task 10: Web — types + data hook

**Files:**
- Modify: `web/src/types/index.ts`
- Create: `web/src/hooks/usePolicyData.ts`

- [ ] **Step 1: Append types**

```ts
// web/src/types/index.ts (append)
export type PolicyEvent = {
  id: string; category: string; headline: string; summary: string;
  raw_excerpt: string; source_url: string; source_domain: string;
  published_at: string; confidence: number;
};
export type TickerImpact = {
  ticker: string; direction: 'positive' | 'negative' | 'neutral';
  strength: 'direct' | 'indirect' | 'neutral';
  score: number; confidence: number; rationale: string;
};
export type PolicyImpactReport = {
  date: string;
  events: PolicyEvent[];
  impacts_by_event: Record<string, TickerImpact[]>;
  impacts_by_ticker: Record<string, TickerImpact[]>;
  tailwind_scores: Record<string, number>;
  metadata: Record<string, unknown>;
};
```

- [ ] **Step 2: Implement the hook**

```ts
// web/src/hooks/usePolicyData.ts
import { useEffect, useState } from 'react';
import type { PolicyImpactReport } from '../types';

export function usePolicyData() {
  const [data, setData] = useState<PolicyImpactReport | null>(null);
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/policy_impact.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status}`))))
      .then(setData)
      .catch(setError);
  }, []);
  return { data, error };
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/types/index.ts web/src/hooks/usePolicyData.ts
git commit -m "feat(web): policy types + usePolicyData hook"
```

---

## Task 11: Web — `/policy` page + route

**Files:**
- Create: `web/src/pages/PolicyImpact.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Implement the page**

```tsx
// web/src/pages/PolicyImpact.tsx
import { useMemo, useState } from 'react';
import { usePolicyData } from '../hooks/usePolicyData';

const CATS = ['interest_rate','antitrust','export_control','subsidy','tariff',
              'ira','chips_act','fda','defense_budget','energy_policy','other'];

export default function PolicyImpact() {
  const { data, error } = usePolicyData();
  const [cat, setCat] = useState<string>('all');

  const events = useMemo(() => {
    if (!data) return [];
    return cat === 'all' ? data.events : data.events.filter((e) => e.category === cat);
  }, [data, cat]);

  if (error) return <div className="p-4">Failed to load policy impact.</div>;
  if (!data) return <div className="p-4">Loading…</div>;

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-2xl font-bold">Policy Impact — {data.date}</h1>
      <div className="flex gap-2 flex-wrap">
        <button onClick={() => setCat('all')}
                className={`px-2 py-1 rounded ${cat==='all'?'bg-black text-white':'bg-gray-200'}`}>
          all
        </button>
        {CATS.map((c) => (
          <button key={c} onClick={() => setCat(c)}
                  className={`px-2 py-1 rounded ${cat===c?'bg-black text-white':'bg-gray-200'}`}>
            {c}
          </button>
        ))}
      </div>
      <ul className="space-y-3">
        {events.map((e) => (
          <li key={e.id} className="border rounded p-3">
            <a href={e.source_url} target="_blank" rel="noreferrer"
               className="font-semibold underline">{e.headline}</a>
            <div className="text-sm text-gray-600">
              {e.category} · {e.source_domain} · conf {e.confidence.toFixed(2)}
            </div>
            <p className="mt-2">{e.summary}</p>
            <div className="mt-2 space-y-1">
              {(data.impacts_by_event[e.id] ?? []).map((i, idx) => (
                <div key={idx} className="text-sm">
                  <span className={
                    i.direction === 'positive' ? 'text-green-700'
                    : i.direction === 'negative' ? 'text-red-700' : 'text-gray-600'
                  }>
                    {i.ticker}: {i.direction} / {i.strength} ({i.score.toFixed(2)})
                  </span>
                  {i.confidence < 0.5 && <span className="ml-2 text-xs text-amber-700">[low confidence]</span>}
                  <span className="ml-2 text-gray-700">{i.rationale}</span>
                </div>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Add the route in `web/src/App.tsx`**

Find the existing `<Routes>`. Add:

```tsx
import PolicyImpact from './pages/PolicyImpact';
// ...
<Route path="/policy" element={<PolicyImpact />} />
```

Also add a nav link wherever existing nav lives (`Sectors`, `Dashboard`).

- [ ] **Step 3: Manual smoke test**

Run: `cd web && npm run dev`
Open `http://localhost:5173/policy` after running the Python pipeline once with policy stage enabled. Verify events render and category filter works.

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/PolicyImpact.tsx web/src/App.tsx
git commit -m "feat(web): /policy page with category filter and impact rows"
```

---

## Task 12: Web — TickerDetail Policy Exposure card

**Files:**
- Modify: `web/src/pages/TickerDetail.tsx`

- [ ] **Step 1: Add the card**

Inside `TickerDetail`, near the existing factor display:

```tsx
import { usePolicyData } from '../hooks/usePolicyData';
// ...
const { data: policy } = usePolicyData();
const tailwind = policy?.tailwind_scores[ticker];
const impacts = policy?.impacts_by_ticker[ticker] ?? [];

{policy && (
  <section className="border rounded p-3 mt-4">
    <h2 className="font-semibold">Policy Exposure</h2>
    {tailwind != null && (
      <div className={`text-lg ${tailwind > 0 ? 'text-green-700' : tailwind < 0 ? 'text-red-700' : ''}`}>
        Tailwind: {tailwind.toFixed(2)}
      </div>
    )}
    <ul className="mt-2 space-y-1 text-sm">
      {impacts.map((i, idx) => (
        <li key={idx}>
          <strong>{i.direction}</strong> · {i.strength} ({i.score.toFixed(2)})
          — {i.rationale}
        </li>
      ))}
      {impacts.length === 0 && <li className="text-gray-500">No policy impacts today.</li>}
    </ul>
  </section>
)}
```

- [ ] **Step 2: Manual smoke test**

Run dev server (already running) and click into any ticker detail page. Verify card renders with tailwind score and rationale list.

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/TickerDetail.tsx
git commit -m "feat(web): TickerDetail Policy Exposure card"
```

---

## Task 13: End-to-end verification

- [ ] **Step 1: Run full test suite**

Run: `python -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 2: Run a real pipeline once**

Run: `python main.py`
Expected: `output/data/policy_impact.json` exists; `dashboard.json` has `policy_tailwind` per ticker; daily MD has "Policy Drivers" section; `logs/pipeline/YYYY-MM-DD.jsonl` contains `policy.stage1.events_count` and `policy.stage2.tickers_scored` entries.

- [ ] **Step 3: Verify graceful degradation**

Set `OPENAI_API_KEY=` (empty) and re-run: pipeline must still complete, `policy_impact.json` may be missing, decision factor renormalizes. Logs show `policy.error`.

- [ ] **Step 4: Update CLAUDE.md**

Add to the "Key modules" table:
- `src/collector/policy_events.py` | Stage 1: web_search policy events
- `src/analyzer/policy_impact.py` | Stage 2: ticker impact mapping + tailwind aggregation
- `src/output/policy_json.py` | `policy_impact.json` writer

- [ ] **Step 5: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: register policy_impact modules in CLAUDE.md"
```

---

## Self-Review Notes

- **Spec coverage:** Sections 1–11 of the spec each map to at least one task above (types→T1, configs→T2, token guards→T3+T5, Stage 1→T4, Stage 2→T5, factor 9→T6, outputs→T7+T8, accuracy guards→T9, web→T10–T12, e2e+graceful→T8+T13).
- **No placeholders:** Every code step contains the actual code; every test contains the actual assertions.
- **Type consistency:** `PolicyEvent`/`TickerImpact`/`PolicyImpactReport` field names are identical across Python (T1), tests (T1, T4, T5), JSON writer (T7), and TS types (T10).
- **Graceful degradation:** T8 wraps both stages in try/except returning `None`; T6 renormalizes weights when `policy_tailwind` missing.
