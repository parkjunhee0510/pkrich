"""Stage 2 of the policy/regulation impact pipeline.

Maps policy events to per-ticker impacts via a chunked LLM call. Pure helpers
(``prefilter_candidates``, ``normalize_score``, ``aggregate_tailwind``) sit
beside the side-effecting ``_openai_map`` so unit tests can mock the LLM.

Score semantics (per spec section 3):
- ``direct``   |score| ∈ [0.7, 1.0]
- ``indirect`` |score| ∈ [0.3, 0.5]
- ``neutral``  score = 0
- aggregate is the confidence-weighted sum of impacts with confidence ≥ 0.5,
  clipped to [-1.0, +1.0].
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from src.types import POLICY_CATEGORIES, PolicyEvent, PolicyImpactReport, TickerImpact
from src.utils.token_budget import count_tokens, split_into_chunks
from src.utils.pipeline_logging import record_pipeline_event


_DIRECT_BAND = (0.7, 1.0)
_INDIRECT_BAND = (0.3, 0.5)
_CONFIDENCE_FLOOR = 0.5


def normalize_score(direction: str, strength: str, raw: float) -> float:
    if strength == "neutral" or direction == "neutral":
        return 0.0
    band = _DIRECT_BAND if strength == "direct" else _INDIRECT_BAND
    magnitude = max(band[0], min(band[1], abs(raw)))
    return magnitude if direction == "positive" else -magnitude


def prefilter_candidates(
    events: list[PolicyEvent],
    ticker_ctx: dict,
    category_to_sectors: dict,
) -> dict[str, list[str]]:
    """For each event, return the candidate tickers that share a relevant sector.

    Events whose category has no mapping (e.g. ``other``) keep the full ticker
    universe so the LLM can still reason about cross-sector impact.
    """

    candidates: dict[str, list[str]] = {}
    for event in events:
        sectors = set(category_to_sectors.get(event.category) or [])
        if not sectors:
            candidates[event.id] = list(ticker_ctx.keys())
            continue
        candidates[event.id] = [
            ticker for ticker, ctx in ticker_ctx.items()
            if ctx.get("sector") in sectors
        ]
    return candidates


def aggregate_tailwind(
    by_ticker: dict[str, list[TickerImpact]],
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ticker, impacts in by_ticker.items():
        running = 0.0
        for impact in impacts:
            if impact.confidence < _CONFIDENCE_FLOOR:
                continue
            running += impact.score * impact.confidence
        scores[ticker] = max(-1.0, min(1.0, round(running, 4)))
    return scores


def _ticker_context_compact(ticker: str, ctx: dict) -> dict:
    return {
        "ticker": ticker,
        "sector": ctx.get("sector"),
        "business": (ctx.get("business") or "")[:160],
        "exposure": list((ctx.get("exposure") or []))[:5],
        "china_revenue_pct": ctx.get("china_revenue_pct", 0),
    }


def _openai_map(
    events_chunk: list[PolicyEvent],
    candidates: list[dict],
    model_profile: str,
) -> dict[str, list[dict]]:
    """Call LLM to map a (events × candidate tickers) chunk → impacts. Mocked in tests."""

    from openai import OpenAI

    from src.utils.config import load_yaml_mapping

    client = OpenAI()
    models_cfg = load_yaml_mapping("config/models.yaml", optional=True) or {}
    profile = (models_cfg.get("profiles") or {}).get(model_profile) or {}
    model = profile.get("model", "gpt-5.4")

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
                            "direction": {
                                "type": "string",
                                "enum": ["positive", "negative", "neutral"],
                            },
                            "strength": {
                                "type": "string",
                                "enum": ["direct", "indirect", "neutral"],
                            },
                            "score": {"type": "number"},
                            "confidence": {"type": "number"},
                            "rationale": {"type": "string"},
                        },
                        "required": [
                            "ticker", "direction", "strength",
                            "score", "confidence", "rationale",
                        ],
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
             "summary": e.summary}
            for e in events_chunk
        ],
        "candidates": candidates,
        "instructions": (
            "For each event, identify which candidate tickers face direct, "
            "indirect, or neutral impact. Use rationale to cite the specific "
            "exposure (e.g., 'China revenue 17%'). confidence in [0,1]."
        ),
    }

    response = client.responses.create(
        model=model,
        input=json.dumps(prompt),
        text={
            "format": {
                "type": "json_schema",
                "name": "impacts",
                "schema": schema,
                "strict": True,
            },
        },
    )
    payload = json.loads(response.output_text)
    return payload.get("impacts_by_event", {}) or {}


def _coerce_impact(item: dict, allowed_tickers: set[str]) -> TickerImpact | None:
    ticker = item.get("ticker")
    if not ticker or ticker not in allowed_tickers:
        return None
    direction = item.get("direction", "neutral")
    if direction not in {"positive", "negative", "neutral"}:
        return None
    strength = item.get("strength", "neutral")
    if strength not in {"direct", "indirect", "neutral"}:
        return None
    try:
        raw_score = float(item.get("score", 0.0))
        confidence = float(item.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    return TickerImpact(
        ticker=ticker,
        direction=direction,
        strength=strength,
        score=normalize_score(direction, strength, raw_score),
        confidence=max(0.0, min(1.0, confidence)),
        rationale=(item.get("rationale") or "")[:200],
    )


def map_impacts(
    events: list[PolicyEvent],
    ticker_ctx: dict,
    category_to_sectors: dict,
    chunk_size: int = 25,
    model_profile: str = "deep",
    today: str | None = None,
) -> PolicyImpactReport:
    started = time.time()
    candidate_map = prefilter_candidates(events, ticker_ctx, category_to_sectors)

    impacts_by_event: dict[str, list[TickerImpact]] = {}
    impacts_by_ticker: dict[str, list[TickerImpact]] = {}
    tokens_in_total = 0
    chunks_attempted = 0
    chunks_failed = 0

    union_candidates = sorted(
        {t for tickers in candidate_map.values() for t in tickers}
    )
    chunks = split_into_chunks(union_candidates, size=chunk_size) or [[]]

    for chunk in chunks:
        if not chunk:
            continue
        compact = [
            _ticker_context_compact(t, ticker_ctx[t])
            for t in chunk if t in ticker_ctx
        ]
        chunk_set = set(chunk)
        chunk_events = [
            e for e in events
            if any(t in candidate_map.get(e.id, []) for t in chunk_set)
        ]
        if not chunk_events:
            continue

        chunks_attempted += 1
        try:
            tokens_in_total += count_tokens(
                json.dumps(compact) + json.dumps([e.summary for e in chunk_events]),
                hard_limit=200_000,
            )
        except Exception:
            # Token counting failure should not abort — keep going.
            pass

        try:
            raw = _openai_map(chunk_events, compact, model_profile)
        except Exception as exc:
            chunks_failed += 1
            record_pipeline_event(
                "policy.analyzer", "error", "chunk_failed",
                error=str(exc),
                chunk_size=len(chunk),
                event_count=len(chunk_events),
            )
            continue

        for event_id, items in raw.items():
            impacts_by_event.setdefault(event_id, [])
            for item in items or []:
                impact = _coerce_impact(item, chunk_set)
                if impact is None:
                    continue
                impacts_by_event[event_id].append(impact)
                impacts_by_ticker.setdefault(impact.ticker, []).append(impact)

    tailwind = aggregate_tailwind(impacts_by_ticker)
    report_date = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return PolicyImpactReport(
        date=report_date,
        events=list(events),
        impacts_by_event=impacts_by_event,
        impacts_by_ticker=impacts_by_ticker,
        tailwind_scores=tailwind,
        metadata={
            "tokens_in": tokens_in_total,
            "model_profile": model_profile,
            "duration_ms": int((time.time() - started) * 1000),
            "chunks": len(chunks),
            "chunks_attempted": chunks_attempted,
            "chunks_failed": chunks_failed,
            "categories": sorted({e.category for e in events}),
        },
    )


__all__ = [
    "POLICY_CATEGORIES",
    "aggregate_tailwind",
    "map_impacts",
    "normalize_score",
    "prefilter_candidates",
]
