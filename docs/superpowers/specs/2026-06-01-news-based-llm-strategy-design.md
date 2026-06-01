# News-Based LLM Strategy Design

Date: 2026-06-01

## Summary

Add a news-aware layer to the existing strategy simulator. The first user-facing step is to make entry candidates easier to trust by showing the news evidence behind each candidate. The second step is to run a news-only shadow strategy that tracks whether LLM-interpreted news signals produce useful 1D, 5D, and 20D forward returns.

The feature remains observational. It does not place trades, automate trading, or present news scores as standalone financial advice.

## Current Context

The project already exports news and LLM evidence through the research pipeline:

- `key_news`
- `news_references`
- `news_tone`
- `catalyst_tag`
- `catalyst_recency`
- `llm_direction`
- `factor_reasoning_json`
- `confidence_meta_json`
- `search_evidence_score`

The strategy simulator currently ranks entry candidates primarily from latest `final_action=BUY`, candidate status, conviction, signal date, and ticker tiebreaks. News and catalyst information influence upstream conviction, but the backtest screen does not yet explain the news basis directly.

## Goals

1. Show why an entry candidate has news support.
2. Make the candidate list more explainable without changing the core BUY selection logic at first.
3. Add a deterministic news evidence score that can be exported and tested.
4. Add a news-only shadow strategy so the app can measure whether news-driven signals have historical value.
5. Keep all outputs static and reproducible for the existing daily pipeline and web app.

## Non-Goals

- No real-time news monitoring.
- No broker integration or order placement.
- No intraday strategy.
- No paid data dependency.
- No replacement of the existing recommendation engine in the first iteration.
- No LLM calls inside the simulator. The simulator should consume already-produced analysis fields.

## User Experience

### Entry Candidate Evidence

Each entry candidate should show compact news evidence beside the current BUY and conviction details.

Example:

```text
NXT
BUY - conviction 67 - waiting for next open
News support: strong
Policy tailwind - LLM bull aligned - recent catalyst
```

If news support is weak:

```text
BUY signal exists, but news support is weak - limited source evidence
```

The UI should avoid long paragraphs in the candidate list. It should use small chips or short reason lines that explain the ranking quickly.

### News Shadow Strategy

The backtest page should later include a separate "News Shadow" section. It compares news-derived virtual signals against forward returns without changing the primary strategy recommendation.

Example metrics:

```text
Strong news + LLM bull
5D avg +3.2% - 20D avg +8.4% - win rate 64% - completed 42/70
```

## Data Contract

Entry candidates in `strategy_simulator.json` should gain a `news_evidence` object.

```json
{
  "news_evidence": {
    "score": 78.0,
    "strength": "strong",
    "tone": "bullish",
    "llm_direction": "bull",
    "llm_alignment": "aligned",
    "catalyst_tag": "earnings",
    "catalyst_recency_score": 20.0,
    "source_count": 3,
    "has_recent_catalyst": true,
    "has_hard_catalyst": true,
    "reason_chips": [
      "positive_news",
      "llm_bull_aligned",
      "recent_catalyst"
    ],
    "summary": "Positive news, LLM bull alignment, and a recent catalyst support this BUY candidate."
  }
}
```

Fields should be nullable or defaulted when generated data is missing. Missing news should produce a valid payload with `strength: "insufficient"` rather than failing the simulator.

## News Evidence Score V1

The score should be deterministic and explainable. It should use fields already available in exported analysis rows.

Suggested scoring:

| Component | Rule | Points |
|---|---|---:|
| News tone | bullish/positive | +20 |
| News tone | bearish/negative | -20 |
| LLM direction | bull | +20 |
| LLM direction | bear | -20 |
| LLM alignment | signal bull + LLM bull | +10 |
| Recent catalyst | catalyst recency positive or recent catalyst present | +15 |
| Hard catalyst | earnings, SEC, IR, guidance, contract, policy tailwind | +10 |
| Source coverage | 2+ references or evidence sources | +10 |
| Search evidence | positive search evidence score | +5 |
| Stale or missing news | no usable news evidence | -10 |

Clamp the final score to `0..100`.

Strength labels:

- `strong`: score >= 75
- `moderate`: score >= 55 and < 75
- `weak`: score >= 35 and < 55
- `insufficient`: score < 35 or missing critical evidence

The scoring should be transparent in output through `reason_chips`.

## Shadow Strategy Rules

The first news shadow strategy should be intentionally simple:

```text
Enter when:
- news_evidence.score >= 70
- llm_direction == bull
- news_tone is positive/bullish or a recent hard catalyst exists

Entry:
- next trading day open

Evaluation:
- forward 1D, 5D, and 20D returns
- completed count vs total count
- average return
- win rate where return > 0

No portfolio sizing in V1:
- This is signal-quality tracking, not a portfolio simulation.
```

This keeps the first shadow strategy comparable to the existing recommendation performance tracking.

## Architecture

### Backend

Add a small utility focused on news evidence normalization and scoring. It should not know about React or chart rendering.

Possible location:

- `src/utils/news_evidence.py`

Responsibilities:

- Normalize tone and direction labels across English/Korean/generated variants.
- Extract catalyst recency, catalyst tag, source counts, and search evidence from a signal row.
- Return a stable `news_evidence` dict.
- Return reason chips that explain the score.

The strategy simulator should call this helper when building candidate payloads. It should not duplicate news scoring logic inline.

### Output

`strategy_simulator.json` should include `news_evidence` for each entry candidate.

Future shadow output can be added under a top-level section:

```json
{
  "news_shadow": {
    "strategies": [
      {
        "id": "strong_news_llm_bull",
        "label": "Strong news + LLM bull",
        "summary": {
          "avg_return_1d": 0.012,
          "avg_return_5d": 0.032,
          "avg_return_20d": 0.084,
          "win_rate_20d": 0.64,
          "completed_20d": 42,
          "total": 70
        }
      }
    ]
  }
}
```

### Frontend

The backtest candidate UI should render:

- News strength label.
- A short summary line.
- 2 to 4 reason chips.
- Fallback text when no evidence is available.

The news evidence should be supportive context. It should not visually overpower the core candidate status, conviction, and entry timing.

## Error Handling

- Missing `news_tone`: use neutral.
- Missing `llm_direction`: use unknown.
- Missing references: source count is 0.
- Invalid score components: ignore component and add no points.
- Unknown catalyst tags: allow them but do not classify as hard catalyst unless mapped.
- Malformed JSON in factor or confidence metadata: treat as absent evidence.

The simulator should still produce a valid payload when all news fields are missing.

## Testing

### Unit Tests

Add tests for the news evidence helper:

- Bullish tone + LLM bull + recent hard catalyst returns strong evidence.
- Bearish tone + LLM bear returns weak or insufficient evidence.
- Missing news fields returns insufficient evidence without raising.
- Korean and English label variants normalize consistently.
- Score clamps to `0..100`.

### Simulator Tests

Add tests that candidate payloads include:

- `news_evidence.score`
- `news_evidence.strength`
- `news_evidence.reason_chips`
- stable fallback values when source news is missing

### Frontend Tests

Add or extend `StrategySimulatorPanel` tests:

- Strong news support appears on candidate cards/table.
- Weak or missing news support renders a clear fallback.
- Existing candidate ranking and status text still render.

### Build Verification

Run:

```powershell
npm --prefix web test -- StrategySimulatorPanel
npm --prefix web run build
python -m pytest tests/test_strategy_simulator.py tests/test_strategy_simulator_output.py
```

Adjust exact test commands to the final touched files.

## Rollout Plan

1. Add deterministic news evidence scoring helper.
2. Attach `news_evidence` to strategy simulator entry candidates.
3. Render news evidence in the candidate UI.
4. Add health/schema validation for the new candidate evidence shape.
5. Add the news shadow strategy output in a follow-up change after the evidence UI is stable.

## Open Decisions

Use the conservative sequence above:

1. Show news evidence first.
2. Add news shadow performance second.
3. Do not alter primary BUY ranking until shadow results prove useful.

This avoids hiding current behavior behind an unproven news score while still making the app much more explainable.
