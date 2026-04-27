# PM Queue Korean-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PM review queue output render in Korean-first form across generated JSON, API payloads, and existing web consumers without changing official decision logic.

**Architecture:** Keep the change isolated to `src/output/pm_view.py`, where PM queue text is already derived. Add deterministic helper functions for Korean event-label normalization and Korean guidance-copy generation, then lock behavior with focused tests and a real pipeline smoke check.

**Tech Stack:** Python, pytest, existing output pipeline, JSON artifacts under `output/data/`

---

## File Map

- Modify: `src/output/pm_view.py`
  - Responsibility: build deterministic PM review queue payloads and human-readable PM copy
- Modify: `tests/test_pm_view.py`
  - Responsibility: lock Korean-first PM queue text behavior and event-label translation
- Inspect after implementation: `output/data/index.json`
  - Responsibility: latest index payload consumed by API and web
- Inspect after implementation: `output/data/dashboard_history.json`
  - Responsibility: dashboard history payload with day-level `pm_view`

### Task 1: Lock Korean-First PM Queue Behavior With Tests

**Files:**
- Modify: `tests/test_pm_view.py`
- Inspect: `src/output/pm_view.py`

- [ ] **Step 1: Write the failing test for Korean swap and event copy**

```python
    def test_build_pm_view_renders_korean_swap_and_event_copy(self) -> None:
        analyses = [
            _analysis(
                'NVDA',
                sector='Technology',
                upcoming_events=[
                    {'type': 'earnings', 'label': 'Earnings', 'date': '2026-04-29', 'days_until': '5', 'timing': 'AMC'},
                ],
            ),
            _analysis('AVGO', sector='Technology'),
        ]

        pm_view = build_pm_view(
            analyses,
            as_of='2026-04-24',
            portfolio_summary=_portfolio_summary('NVDA'),
            portfolio_risk={
                'risk_grade': 'D',
                'positions_by_weight': [
                    {'ticker': 'NVDA', 'weight': 0.42, 'sector': 'Technology'},
                ],
            },
            decision_map={
                'NVDA': _decision('watch', 58),
                'AVGO': _decision('buy', 82),
            },
        )

        swap_item = pm_view['swap_candidates'][0]
        event_item = pm_view['event_exposure_items'][0]

        self.assertIn('교체', swap_item['summary'])
        self.assertIn('동일 섹터', swap_item['overlap_context'])
        self.assertIn('확신도', ' '.join(swap_item['reasons']))
        self.assertEqual(event_item['event_label'], '실적 발표')
        self.assertIn('이벤트', event_item['summary'])
        self.assertIn('5일', ' '.join(event_item['reasons']))
```

- [ ] **Step 2: Write the failing test for Korean empty states and unknown event fallback**

```python
    def test_build_pm_view_renders_korean_empty_states_and_unknown_event_fallback(self) -> None:
        pm_view = build_pm_view(
            [
                _analysis(
                    'NVDA',
                    sector='Technology',
                    upcoming_events=[
                        {'type': 'roadshow', 'label': 'Capital Markets Day', 'date': '2026-04-26', 'days_until': '2'},
                    ],
                ),
                _analysis('AVGO', sector='Technology'),
            ],
            as_of='2026-04-24',
            portfolio_summary=_portfolio_summary('NVDA'),
            portfolio_risk={},
            decision_map={
                'NVDA': _decision('watch', 58),
                'AVGO': _decision('buy', 82),
            },
        )

        self.assertIn('포트폴리오', build_pm_view(
            [_analysis('AVGO', sector='Technology')],
            as_of='2026-04-24',
            portfolio_summary=None,
            portfolio_risk={},
            decision_map={'AVGO': _decision('buy', 82)},
        )['empty_states']['swap_candidates'])
        self.assertEqual(pm_view['event_exposure_items'][0]['event_label'], '주요 일정')
        self.assertNotIn('Capital Markets Day', pm_view['event_exposure_items'][0]['summary'])
```

- [ ] **Step 3: Run test file to verify it fails before implementation**

Run: `PYTHONPATH=. pytest tests/test_pm_view.py -q`

Expected: FAIL because current PM queue strings are still English and event labels are not translated.

- [ ] **Step 4: Commit the failing test**

```bash
git add tests/test_pm_view.py
git commit -m "test: lock Korean-first PM queue copy"
```

### Task 2: Implement Deterministic Korean PM Queue Copy

**Files:**
- Modify: `src/output/pm_view.py`
- Test: `tests/test_pm_view.py`

- [ ] **Step 1: Add event-label normalization helpers**

```python
EVENT_LABEL_TRANSLATIONS = {
    "earnings": "실적 발표",
    "earnings call": "실적 발표",
    "dividend payment date": "배당 지급일",
    "ex-dividend date": "배당락일",
    "fed meeting": "연준 회의",
    "fomc meeting": "연준 회의",
    "cpi release": "CPI 발표",
    "developer conference": "개발자 컨퍼런스",
    "product launch": "신제품 출시",
    "shareholder meeting": "주주총회",
}


def _normalize_event_label(event: Mapping[str, Any]) -> str:
    raw_label = str(event.get("label") or "").strip()
    raw_type = str(event.get("type") or "").strip()
    for candidate in (raw_label, raw_type):
        normalized = EVENT_LABEL_TRANSLATIONS.get(candidate.lower())
        if normalized:
            return normalized
    return "주요 일정"
```

- [ ] **Step 2: Add Korean-safe text helpers for sectors and day counts**

```python
def _display_sector(sector: str) -> str:
    cleaned = str(sector).strip()
    return cleaned if cleaned else "동일 업종"


def _days_phrase(days_until: int) -> str:
    if days_until <= 0:
        return "오늘"
    return f"{days_until}일"
```

- [ ] **Step 3: Rewrite swap candidate copy generation in Korean**

```python
        candidates.append({
            "held_ticker": held_ticker,
            "candidate_ticker": candidate_ticker,
            "swap_candidate_score": score,
            "summary": f"{held_ticker} 대비 {candidate_ticker} 교체 검토가 필요합니다.",
            "reasons": [
                f"{candidate_ticker} 확신도 {candidate_decision.conviction}가 {held_ticker}의 {held_decision.conviction}보다 높습니다.",
                f"동일 섹터 비교로 검토 맥락이 명확합니다: {_display_sector(held_sector)}.",
                (
                    f"{held_ticker} 비중이 포트폴리오 내 {weight:.0%}로 높아 교체 검토 우선순위가 있습니다."
                    if weight > 0
                    else f"{held_ticker}는 현재 보유 익스포저로 유지 타당성 점검이 필요합니다."
                ),
            ],
            "overlap_context": f"동일 섹터: {_display_sector(held_sector)}",
            "review_points": [
                f"{candidate_ticker}가 {held_ticker}보다 더 깔끔한 확신도 근거를 제공하는지 확인하세요.",
                f"{held_ticker} 비중 변경 전 포트폴리오 집중도 영향을 점검하세요.",
            ],
        })
```

- [ ] **Step 4: Rewrite event exposure and queue copy generation in Korean**

```python
        label = _normalize_event_label(event)
        items.append({
            "ticker": ticker,
            "event_risk_score": score,
            "event_label": label,
            "event_date": str(event.get("date", "")),
            "days_until": days_until,
            "summary": f"{ticker}의 {label} 전 이벤트 노출 점검이 필요합니다.",
            "reasons": [
                f"{label} 일정이 {_days_phrase(days_until)} 앞으로 예정돼 있습니다.",
                (
                    f"{ticker} 확신도 {conviction} 구간이라 이벤트 전 점검 우선순위가 높습니다."
                    if conviction
                    else f"{ticker}는 보유 종목이어서 이벤트 전 노출 점검이 필요합니다."
                ),
                (
                    f"{ticker} 비중이 포트폴리오 내 {weight:.0%}입니다."
                    if weight > 0
                    else f"{ticker} 이벤트 전 포지션 규모와 변동성 노출을 확인하세요."
                ),
            ],
            "review_points": [
                f"{ticker} 이벤트 전 포지션 규모가 적절한지 확인하세요.",
                f"{label} 전후 변동성 확대 가능성을 점검하세요.",
            ],
        })
```

- [ ] **Step 5: Rewrite empty-state helpers in Korean without English fallback words**

```python
def _swap_empty_state(held_tickers: set[str], swap_candidates: Sequence[dict[str, Any]]) -> str:
    if swap_candidates:
        return ""
    if not held_tickers:
        return "포트폴리오 보유 종목이 없어 교체 검토 후보를 만들지 않았습니다."
    return "오늘은 동일 섹터 내에서 더 나은 교체 후보가 없습니다."


def _event_empty_state(held_tickers: set[str], event_exposure_items: Sequence[dict[str, Any]]) -> str:
    if event_exposure_items:
        return ""
    if not held_tickers:
        return "포트폴리오 보유 종목이 없어 이벤트 노출 점검 항목이 없습니다."
    return "오늘은 별도로 점검할 단기 이벤트 노출이 없습니다."


def _queue_empty_state(held_tickers: set[str], today_priority_queue: Sequence[dict[str, Any]]) -> str:
    if today_priority_queue:
        return ""
    if not held_tickers:
        return "포트폴리오 보유 종목이 없어 PM 검토 큐를 만들지 않았습니다."
    return "오늘 바로 확인할 PM 우선 검토 항목이 없습니다."
```

- [ ] **Step 6: Run focused PM view tests to verify implementation passes**

Run: `PYTHONPATH=. pytest tests/test_pm_view.py -q`

Expected: PASS with Korean-first assertions succeeding.

- [ ] **Step 7: Commit the implementation**

```bash
git add src/output/pm_view.py tests/test_pm_view.py
git commit -m "feat: localize PM queue output to Korean"
```

### Task 3: Verify Real Output Chain

**Files:**
- Inspect: `output/data/index.json`
- Inspect: `output/data/dashboard_history.json`
- Inspect: `src/api/main.py`

- [ ] **Step 1: Run the smallest contract tests that guard PM output shape**

Run: `PYTHONPATH=. pytest tests/test_output_schema.py tests/test_sharded_export.py -k "pm_view or sharded_index_pm_view_matches_populated_snapshot_shape or dashboard_history_pm_view_matches_populated_snapshot_shape" -q`

Expected: PASS and no schema regressions from Korean text values.

- [ ] **Step 2: Run the real pipeline to regenerate output artifacts**

Run: `python main.py`

Expected: pipeline completes successfully and refreshes `output/data/index.json` plus `output/data/dashboard_history.json`.

- [ ] **Step 3: Inspect generated PM queue text in the latest artifacts**

Run: `rg -n "\"pm_view\"|\"event_label\"|\"summary\"" output/data/index.json output/data/dashboard_history.json`

Expected: matches show Korean PM queue text such as `교체 검토`, `이벤트 노출`, `실적 발표`, and no English boilerplate like `Review` inside PM queue payloads.

- [ ] **Step 4: Commit verification-safe code and docs state**

```bash
git add src/output/pm_view.py tests/test_pm_view.py
git commit -m "chore: verify Korean PM queue output"
```

## Self-Review

- Spec coverage: covered Korean-first values, event-label translation, Korean empty states, deterministic output, and real pipeline artifact verification.
- Placeholder scan: no `TBD`, `TODO`, or vague implementation steps remain.
- Type consistency: all tasks use existing `pm_view` field names and keep schema keys unchanged.
