# PM Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an additive PM review workflow that surfaces swap-review candidates, event exposure reviews, and a daily priority queue without overriding the existing `buy/watch/avoid` decision system.

**Architecture:** Build a thin backend derivation layer that reads finalized output-stage inputs and produces a new `pm_view` payload. Export that payload through existing dashboard JSON and API paths, then render a scan-oriented queue on `Dashboard` and a deeper review surface on `Portfolio`.

**Tech Stack:** Python, pytest, FastAPI, React, TypeScript, Vite

---

### Task 1: Build PM derivation and backend tests

**Files:**
- Create: `src/output/pm_view.py`
- Modify: `src/output/json_export.py`
- Test: `tests/test_pm_view.py`

- [ ] **Step 1: Write the failing backend derivation tests**

```python
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from src.output.pm_view import build_pm_view


def _analysis(
    ticker: str,
    sector: str,
    conviction: float,
    *,
    days_until: int,
    action: str = "watch",
) -> SimpleNamespace:
    return SimpleNamespace(
        ticker=ticker,
        data_snapshot={"Sector": sector},
        upcoming_events=[{"type": "earnings", "label": "Earnings", "date": "2026-04-30", "days_until": str(days_until)}],
        decision=SimpleNamespace(action=action, conviction=conviction),
    )


def test_build_pm_view_generates_swap_event_and_priority_sections() -> None:
    portfolio_summary = SimpleNamespace(
        positions=[
            SimpleNamespace(
                ticker="NVDA",
                shares=10,
                avg_cost=100.0,
                currency="USD",
                market_price=120.0,
                market_value=1200.0,
                cost_basis=1000.0,
                unrealized_pnl=200.0,
                unrealized_return_pct=20.0,
            )
        ]
    )
    portfolio_risk = {
        "positions_by_weight": [{"ticker": "NVDA", "weight_pct": 28.0, "market_value": 1200.0, "atr_risk_usd": 90.0}],
        "correlation_pairs": [{"ticker_1": "NVDA", "ticker_2": "AMD", "correlation": "0.91", "warning": "high"}],
        "risk_grade": "C",
    }
    held = _analysis("NVDA", "Semiconductors", 62.0, days_until=2, action="watch")
    candidate = _analysis("AVGO", "Semiconductors", 79.0, days_until=12, action="buy")

    payload = build_pm_view(
        analyses=[held, candidate],
        run_date=date(2026, 4, 24),
        portfolio_summary=portfolio_summary,
        portfolio_risk=portfolio_risk,
    )

    assert payload["swap_candidates"][0]["held_ticker"] == "NVDA"
    assert payload["event_exposure_items"][0]["ticker"] == "NVDA"
    assert payload["today_priority_queue"][0]["priority_type"] in {"swap review", "event review", "risk warning"}
    assert payload["today_priority_queue"][0]["today_priority_score"] >= payload["today_priority_queue"][-1]["today_priority_score"]


def test_build_pm_view_returns_explanatory_empty_state_for_missing_portfolio() -> None:
    payload = build_pm_view(
        analyses=[],
        run_date=date(2026, 4, 24),
        portfolio_summary=None,
        portfolio_risk={},
    )

    assert payload["swap_candidates"] == []
    assert payload["event_exposure_items"] == []
    assert payload["today_priority_queue"] == []
    assert "No swap review candidates today" in payload["empty_states"]["swap_candidates"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pm_view.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.output.pm_view'`

- [ ] **Step 3: Write minimal PM derivation module**

```python
from __future__ import annotations

from datetime import date
from typing import Any


def build_pm_view(
    *,
    analyses: list[Any],
    run_date: date,
    portfolio_summary: Any | None,
    portfolio_risk: dict[str, Any] | None,
) -> dict[str, Any]:
    portfolio_risk = portfolio_risk or {}
    holdings = {
        str(position.ticker).upper(): position
        for position in getattr(portfolio_summary, "positions", []) or []
    }
    non_held = [analysis for analysis in analyses if str(getattr(analysis, "ticker", "")).upper() not in holdings]
    held = [analysis for analysis in analyses if str(getattr(analysis, "ticker", "")).upper() in holdings]

    swap_candidates = []
    event_exposure_items = []

    for analysis in held:
        ticker = str(getattr(analysis, "ticker", "")).upper()
        candidate = next((item for item in non_held if _same_sector(analysis, item)), None)
        if candidate is not None:
            swap_candidates.append(
                {
                    "held_ticker": ticker,
                    "candidate_ticker": str(getattr(candidate, "ticker", "")).upper(),
                    "swap_candidate_score": _swap_candidate_score(analysis, candidate, portfolio_risk),
                    "summary": f"Review {ticker} against {candidate.ticker} for similar exposure with cleaner setup.",
                    "reasons": [
                        "Same sector comparison",
                        "Higher candidate conviction",
                        "Held name carries more portfolio pressure",
                    ],
                    "overlap_context": _sector_label(analysis),
                    "review_points": [
                        "Check conviction delta",
                        "Check event calendar",
                        "Check concentration impact",
                    ],
                }
            )

        event = _next_event(analysis)
        if event is not None:
            event_exposure_items.append(
                {
                    "ticker": ticker,
                    "event_risk_score": _event_risk_score(analysis, portfolio_risk),
                    "event_label": event.get("label", event.get("type", "Event")),
                    "event_date": event.get("date", ""),
                    "days_until": event.get("days_until", ""),
                    "summary": f"Review {ticker} ahead of {event.get('label', 'event')}.",
                    "reasons": [
                        f"Event in D-{event.get('days_until', 'N/A')}",
                        "Held position contributes to portfolio exposure",
                    ],
                    "review_points": [
                        "Check announcement timing",
                        "Check overlapping exposure",
                        "Check volatility context",
                    ],
                }
            )

    priority_queue = _build_priority_queue(swap_candidates, event_exposure_items, portfolio_risk)
    return {
        "as_of": run_date.isoformat(),
        "swap_candidates": sorted(swap_candidates, key=lambda item: item["swap_candidate_score"], reverse=True)[:5],
        "event_exposure_items": sorted(event_exposure_items, key=lambda item: item["event_risk_score"], reverse=True)[:5],
        "today_priority_queue": priority_queue[:8],
        "empty_states": {
            "swap_candidates": "No swap review candidates today. Current holdings remain relatively stable on conviction and event calendar.",
            "event_exposure_items": "No urgent event exposure reviews today.",
            "today_priority_queue": "No PM review items today.",
        },
    }


def _same_sector(left: Any, right: Any) -> bool:
    return _sector_label(left) and _sector_label(left) == _sector_label(right)


def _sector_label(analysis: Any) -> str:
    snapshot = getattr(analysis, "data_snapshot", {}) or {}
    return str(snapshot.get("Sector", "")).strip()


def _conviction(analysis: Any) -> float:
    decision = getattr(analysis, "decision", None)
    return float(getattr(decision, "conviction", 0.0) or 0.0)


def _swap_candidate_score(held: Any, candidate: Any, portfolio_risk: dict[str, Any]) -> float:
    risk_bonus = 8.0 if any(item.get("ticker") == getattr(held, "ticker", "") for item in portfolio_risk.get("positions_by_weight", [])) else 0.0
    return round(max(0.0, (_conviction(candidate) - _conviction(held)) + risk_bonus), 2)


def _event_risk_score(analysis: Any, portfolio_risk: dict[str, Any]) -> float:
    event = _next_event(analysis)
    if event is None:
        return 0.0
    days_until = int(str(event.get("days_until", "99")) or 99)
    timing_score = max(0, 10 - days_until)
    concentration_bonus = 6.0 if any(item.get("ticker") == getattr(analysis, "ticker", "") for item in portfolio_risk.get("positions_by_weight", [])) else 0.0
    return round(timing_score + concentration_bonus, 2)


def _next_event(analysis: Any) -> dict[str, Any] | None:
    events = getattr(analysis, "upcoming_events", []) or []
    normalized = [event for event in events if isinstance(event, dict)]
    if not normalized:
        return None
    normalized.sort(key=lambda event: int(str(event.get("days_until", "999")) or 999))
    return normalized[0]


def _build_priority_queue(
    swap_candidates: list[dict[str, Any]],
    event_exposure_items: list[dict[str, Any]],
    portfolio_risk: dict[str, Any],
) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for item in swap_candidates:
        queue.append(
            {
                "priority_type": "swap review",
                "ticker": item["held_ticker"],
                "related_ticker": item["candidate_ticker"],
                "today_priority_score": round(item["swap_candidate_score"] + 5.0, 2),
                "summary": item["summary"],
                "reasons": item["reasons"],
                "destination": f"/portfolio?ticker={item['held_ticker']}",
            }
        )
    for item in event_exposure_items:
        queue.append(
            {
                "priority_type": "event review",
                "ticker": item["ticker"],
                "today_priority_score": round(item["event_risk_score"] + 4.0, 2),
                "summary": item["summary"],
                "reasons": item["reasons"],
                "destination": f"/portfolio?ticker={item['ticker']}",
            }
        )
    if str(portfolio_risk.get("risk_grade", "")).upper() in {"C", "D"}:
        queue.append(
            {
                "priority_type": "risk warning",
                "ticker": "PORTFOLIO",
                "today_priority_score": 99.0,
                "summary": f"Portfolio risk grade is {portfolio_risk.get('risk_grade')}.",
                "reasons": ["Portfolio-level risk pressure is elevated"],
                "destination": "/portfolio",
            }
        )
    queue.sort(key=lambda item: item["today_priority_score"], reverse=True)
    return queue
```

- [ ] **Step 4: Export `pm_view` through the dashboard JSON writer**

```python
from src.output.pm_view import build_pm_view


def _write_dashboard_jsons(
    latest_path: Path,
    history_path: Path,
    analyses: list[TickerAnalysis],
    run_date: date,
    market_overview: list[dict[str, str]],
    period_changes_by_ticker: dict[str, dict[str, str]],
    portfolio_summary: PortfolioSummary | None,
    signal_stats: dict[str, Any],
    macro_context: dict[str, Any] | None = None,
    portfolio_risk: dict[str, Any] | None = None,
    weekly_summary: WeeklySummaryData | None = None,
    market_regime: MarketRegime | None = None,
    decision_map: dict[str, TickerDecision] | None = None,
    derived_by_ticker: dict[str, dict[str, Any]] | None = None,
    price_history_rows: list[dict[str, str]] | None = None,
    emit_legacy_dashboard: bool = False,
    weekly_summary_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pm_view = build_pm_view(
        analyses=analyses,
        run_date=run_date,
        portfolio_summary=portfolio_summary,
        portfolio_risk=portfolio_risk or {},
    )
    new_day = {
        "date": run_date.isoformat(),
        "market_overview": market_overview,
        "macro_context": macro_context or {},
        "market_regime": _serialize_market_regime(market_regime),
        "portfolio_risk": portfolio_risk or {},
        "portfolio_summary": _serialize_portfolio_summary(portfolio_summary),
        "pm_view": pm_view,
        "tickers": [
            _serialize_analysis(
                a,
                period_changes_by_ticker.get(a.ticker, {"7d": "N/A", "30d": "N/A"}),
                decision=dm.get(a.ticker),
                ticker_derivations=(derived_by_ticker or {}).get(a.ticker),
            )
            for a in analyses
        ],
    }
```

- [ ] **Step 5: Run tests to verify backend passes**

Run: `pytest tests/test_pm_view.py tests/test_output.py -v`
Expected: PASS with new `pm_view` assertions and no regressions in output export tests

- [ ] **Step 6: Commit**

```bash
git add src/output/pm_view.py src/output/json_export.py tests/test_pm_view.py tests/test_output.py
git commit -m "feat: add pm review payload derivation"
```

### Task 2: Wire PM payload through API and schema tests

**Files:**
- Modify: `src/api/main.py`
- Modify: `tests/test_output_schema.py`
- Modify: `tests/test_output.py`

- [ ] **Step 1: Extend schema tests with `pm_view` expectations**

```python
def test_dashboard_payload_includes_pm_view(output_root: Path) -> None:
    payload = json.loads((output_root / "data" / "dashboard.json").read_text(encoding="utf-8"))
    latest_day = payload["days"][0]

    assert "pm_view" in latest_day
    assert set(latest_day["pm_view"]) == {
        "as_of",
        "swap_candidates",
        "event_exposure_items",
        "today_priority_queue",
        "empty_states",
    }
```

- [ ] **Step 2: Run tests to verify they fail on missing API wiring**

Run: `pytest tests/test_output_schema.py tests/test_output.py -v`
Expected: FAIL because `pm_view` is missing from dashboard payloads

- [ ] **Step 3: Update the API daily payload to include `pm_view`**

```python
def _load_dashboard_payload() -> dict[str, Any]:
    index_payload = _load_json(OUTPUT_ROOT / "data" / "index.json", default={})
    if isinstance(index_payload, dict) and index_payload.get("date"):
        return {
            "schema_version": index_payload.get("schema_version"),
            "days": [
                {
                    "date": index_payload.get("date", ""),
                    "market_overview": index_payload.get("market_overview", []),
                    "macro_context": index_payload.get("macro_context", {}),
                    "market_regime": index_payload.get("market_regime", {}),
                    "portfolio_summary": index_payload.get("portfolio_summary"),
                    "portfolio_risk": index_payload.get("portfolio_risk", {}),
                    "pm_view": index_payload.get("pm_view", {}),
                    "tickers": index_payload.get("tickers", []),
                }
            ],
            "signal_stats": index_payload.get("signal_stats", {}),
            "weekly_summary": index_payload.get("weekly_summary", {}),
        }
    return _load_json(OUTPUT_ROOT / "data" / "dashboard.json", default={"days": []})
```

- [ ] **Step 4: Add export assertions for `pm_view` in output tests**

```python
dashboard = json.loads((web_data_dir / "dashboard.json").read_text(encoding="utf-8"))
day = dashboard["days"][0]

self.assertIn("pm_view", day)
self.assertIn("swap_candidates", day["pm_view"])
self.assertIn("event_exposure_items", day["pm_view"])
self.assertIn("today_priority_queue", day["pm_view"])
```

- [ ] **Step 5: Run tests to verify API and schema pass**

Run: `pytest tests/test_output_schema.py tests/test_output.py -v`
Expected: PASS with additive dashboard shape preserved

- [ ] **Step 6: Commit**

```bash
git add src/api/main.py tests/test_output_schema.py tests/test_output.py
git commit -m "feat: expose pm view through dashboard payloads"
```

### Task 3: Render scan-oriented PM queue on Dashboard

**Files:**
- Create: `web/src/components/PmDailyQueue.tsx`
- Modify: `web/src/types/index.ts`
- Modify: `web/src/pages/Dashboard.tsx`

- [ ] **Step 1: Add TypeScript types for `pm_view`**

```ts
export interface PmSwapCandidate {
  held_ticker: string
  candidate_ticker: string
  swap_candidate_score: number
  summary: string
  reasons: string[]
  overlap_context: string
  review_points: string[]
}

export interface PmEventExposureItem {
  ticker: string
  event_risk_score: number
  event_label: string
  event_date: string
  days_until: string
  summary: string
  reasons: string[]
  review_points: string[]
}

export interface PmPriorityQueueItem {
  priority_type: 'swap review' | 'event review' | 'decision change' | 'risk warning' | string
  ticker: string
  related_ticker?: string
  today_priority_score: number
  summary: string
  reasons: string[]
  destination: string
}

export interface PmViewData {
  as_of: string
  swap_candidates: PmSwapCandidate[]
  event_exposure_items: PmEventExposureItem[]
  today_priority_queue: PmPriorityQueueItem[]
  empty_states: {
    swap_candidates: string
    event_exposure_items: string
    today_priority_queue: string
  }
}

export interface DailyEntry {
  date: string
  market_overview: MarketOverviewEntry[]
  macro_context?: MacroContext | null
  market_regime?: MarketRegimeData | null
  portfolio_risk?: PortfolioRisk | null
  portfolio_summary?: PortfolioSummaryData | null
  pm_view?: PmViewData | null
  tickers: TickerAnalysisData[]
}
```

- [ ] **Step 2: Run frontend build to verify the new types fail before component wiring**

Run: `npm run build`
Expected: FAIL with `PmDailyQueue` or `pm_view` usage not implemented yet

- [ ] **Step 3: Create a dedicated dashboard PM queue component**

```tsx
import { Link } from 'react-router-dom'
import type { PmViewData } from '../types'

export function PmDailyQueue({ pmView }: { pmView?: PmViewData | null }) {
  const swapCandidates = pmView?.swap_candidates ?? []
  const eventItems = pmView?.event_exposure_items ?? []
  const priorityQueue = pmView?.today_priority_queue ?? []
  const emptyStates = pmView?.empty_states

  return (
    <section className="dashboard-panel-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>PM Daily Queue</h3>
          <p className="section-kicker">Review-only portfolio manager queue for swaps, event exposure, and today-first checks.</p>
        </div>
      </div>

      <div className="decision-board-analysis-grid">
        <article className="decision-board-panel">
          <span className="decision-board-panel-label">Swap Review Candidates</span>
          {swapCandidates.length > 0 ? (
            <ul className="decision-board-list">
              {swapCandidates.map((item) => (
                <li key={`${item.held_ticker}-${item.candidate_ticker}`}>
                  <strong>{item.held_ticker} vs {item.candidate_ticker}</strong>
                  <span>{item.summary}</span>
                  <span>Score {item.swap_candidate_score.toFixed(1)} | {item.overlap_context}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="decision-board-panel-copy">{emptyStates?.swap_candidates ?? 'No swap review candidates.'}</p>
          )}
        </article>

        <article className="decision-board-panel">
          <span className="decision-board-panel-label">Event Exposure Review</span>
          {eventItems.length > 0 ? (
            <ul className="decision-board-list">
              {eventItems.map((item) => (
                <li key={`${item.ticker}-${item.event_label}-${item.event_date}`}>
                  <strong>{item.ticker} | {item.event_label}</strong>
                  <span>{item.summary}</span>
                  <span>D-{item.days_until} | score {item.event_risk_score.toFixed(1)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="decision-board-panel-copy">{emptyStates?.event_exposure_items ?? 'No urgent event reviews.'}</p>
          )}
        </article>

        <article className="decision-board-panel decision-board-panel-wide">
          <span className="decision-board-panel-label">Today Priority Queue</span>
          {priorityQueue.length > 0 ? (
            <ul className="decision-board-list">
              {priorityQueue.map((item) => (
                <li key={`${item.priority_type}-${item.ticker}-${item.related_ticker ?? ''}`}>
                  <strong>{item.priority_type}</strong>
                  <span>{item.ticker}{item.related_ticker ? ` -> ${item.related_ticker}` : ''}</span>
                  <span>{item.summary}</span>
                  <Link to={item.destination}>Open review</Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="decision-board-panel-copy">{emptyStates?.today_priority_queue ?? 'No PM review items.'}</p>
          )}
        </article>
      </div>
    </section>
  )
}
```

- [ ] **Step 4: Mount the PM queue at the top of `Dashboard`**

```tsx
import { PmDailyQueue } from '../components/PmDailyQueue'

export function Dashboard() {
  const day = days[idx] ?? { date: '', market_overview: [], tickers: [] }

  return (
    <div className="dashboard" data-density={density}>
      <PmDailyQueue pmView={day.pm_view} />
      <MarketOverview items={day.market_overview} />
      <MacroContextBar macroContext={day.macro_context} />
      <MarketRegimeBanner regime={day.market_regime} />
      <TodaySetupBoard cards={topSetupCards} />
      <EarningsBoard sections={earningsBoardSections} />
      <CatalystFeed sections={catalystFeedSections} />
    </div>
  )
}
```

- [ ] **Step 5: Run frontend build to verify Dashboard integration passes**

Run: `npm run build`
Expected: PASS with `pm_view` types resolved and Dashboard rendering successfully

- [ ] **Step 6: Commit**

```bash
git add web/src/components/PmDailyQueue.tsx web/src/types/index.ts web/src/pages/Dashboard.tsx
git commit -m "feat: add dashboard pm daily queue"
```

### Task 4: Add deep review surface on Portfolio and update docs

**Files:**
- Create: `web/src/components/PortfolioActionsReview.tsx`
- Modify: `web/src/pages/Portfolio.tsx`
- Modify: `docs/output.md`
- Test: `tests/test_output_schema.py`

- [ ] **Step 1: Add the portfolio review component with empty-state-safe rendering**

```tsx
import { Link } from 'react-router-dom'
import type { DailyEntry } from '../types'

export function PortfolioActionsReview({ day }: { day: DailyEntry }) {
  const pmView = day.pm_view
  const swaps = pmView?.swap_candidates ?? []
  const events = pmView?.event_exposure_items ?? []

  return (
    <section className="portfolio-risk-panel">
      <div className="section-header-with-kicker">
        <div>
          <h3>Portfolio Actions Review</h3>
          <p className="section-kicker">Deeper review context for held names that need comparison or event checks.</p>
        </div>
      </div>

      <div className="portfolio-risk-grid">
        <div className="portfolio-risk-card">
          <span className="price-action-label">Swap Review Candidates</span>
          {swaps.length > 0 ? (
            <ul className="portfolio-risk-recommendations">
              {swaps.map((item) => (
                <li key={`${item.held_ticker}-${item.candidate_ticker}`}>
                  <strong>{item.held_ticker} vs {item.candidate_ticker}</strong>
                  <span>{item.summary}</span>
                  <span>{item.reasons.join(' | ')}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty">{pmView?.empty_states.swap_candidates ?? 'No swap review candidates.'}</p>
          )}
        </div>

        <div className="portfolio-risk-card">
          <span className="price-action-label">Event Exposure Review</span>
          {events.length > 0 ? (
            <ul className="portfolio-risk-recommendations">
              {events.map((item) => (
                <li key={`${item.ticker}-${item.event_label}-${item.event_date}`}>
                  <strong>{item.ticker} | {item.event_label}</strong>
                  <span>{item.summary}</span>
                  <span>{item.review_points.join(' | ')}</span>
                  <Link to={`/ticker/${item.ticker}`}>Open ticker</Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty">{pmView?.empty_states.event_exposure_items ?? 'No urgent event reviews.'}</p>
          )}
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 2: Mount the review surface above the holdings table**

```tsx
import { PortfolioActionsReview } from '../components/PortfolioActionsReview'

export function Portfolio() {
  return (
    <div className="portfolio-page">
      <div className="dashboard-header">
        <h2>Portfolio {latestDay.date}</h2>
      </div>
      {viewMode === 'summary' ? (
        <>
          <PortfolioActionsReview day={latestDay} />
          <EquityCurveChart days={data.days} />
          <PortfolioRiskPanel risk={latestDay.portfolio_risk} />
          <div className="table-wrap">
            <table className="watchlist-table" />
          </div>
        </>
      ) : (
        <div className="portfolio-editor-shell">{draftHoldings.length}</div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Update the output docs for the additive PM payload**

```md
Per-day dashboard payloads may now include:

- `pm_view` with:
  - `swap_candidates`
  - `event_exposure_items`
  - `today_priority_queue`
  - explanatory `empty_states`

`pm_view` is a presentation and review-support payload. It must not override rule-based `buy/watch/avoid`.
```

- [ ] **Step 4: Add a schema assertion covering the new `pm_view` contract**

```python
day = payload["days"][0]
pm_view = day["pm_view"]

assert isinstance(pm_view["swap_candidates"], list)
assert isinstance(pm_view["event_exposure_items"], list)
assert isinstance(pm_view["today_priority_queue"], list)
assert isinstance(pm_view["empty_states"]["swap_candidates"], str)
```

- [ ] **Step 5: Run focused verification**

Run: `pytest tests/test_pm_view.py tests/test_output.py tests/test_output_schema.py -v`
Expected: PASS

Run: `npm run build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/src/components/PortfolioActionsReview.tsx web/src/pages/Portfolio.tsx docs/output.md tests/test_output_schema.py
git commit -m "feat: add portfolio pm review surfaces"
```
