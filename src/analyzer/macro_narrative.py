"""Run-level macro narrative synthesis.

Calls the LLM once per run to produce a compact, structured macro narrative
that is injected into every ticker prompt. Output is cached per run_date for
24 hours to cap cost at one call per run.

Fails soft: returns an empty dict on any error so prompt assembly degrades
gracefully to the raw macro context.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

from src.types import MarketRegime

logger = logging.getLogger(__name__)

_CACHE_DIR = Path("output/cache")
_MODEL = os.getenv("PKRICH_MACRO_NARRATIVE_MODEL", "gpt-4o-mini")
_FLAG = "PKRICH_MACRO_NARRATIVE"


def build_macro_narrative(
    macro_context: dict[str, Any],
    market_regime: MarketRegime,
    run_date: date,
) -> dict[str, Any]:
    """Return cached or freshly-generated narrative for ``run_date``.

    Structure::

        {
          "headline": "...",
          "three_themes": ["...", "...", "..."],
          "risk_map": "short sentence",
          "what_changed_this_week": "short sentence",
          "source": "llm"|"fallback",
          "model": "gpt-4o-mini"
        }
    """
    if os.getenv(_FLAG, "1") == "0":
        return _fallback(market_regime)

    cache_path = _CACHE_DIR / f"macro_narrative_{run_date.isoformat()}.json"
    cached = _read_cache(cache_path)
    if cached:
        return cached

    if not os.getenv("OPENAI_API_KEY"):
        result = _fallback(market_regime)
        _write_cache(cache_path, result)
        return result

    payload = _build_prompt_payload(macro_context, market_regime)
    try:
        narrative = _call_llm(payload)
    except Exception:
        logger.debug("macro_narrative llm call failed", exc_info=True)
        narrative = None

    if not narrative:
        narrative = _fallback(market_regime)
    else:
        narrative.setdefault("source", "llm")
        narrative.setdefault("model", _MODEL)

    _write_cache(cache_path, narrative)
    return narrative


def _build_prompt_payload(
    macro_context: dict[str, Any],
    market_regime: MarketRegime,
) -> dict[str, Any]:
    # Shrink macro_context to the fields useful for a narrative to keep tokens low.
    keys = [
        "vix", "us10y", "us2y", "us30y", "dxy", "copper", "oil_wti", "gold",
        "yield_curve_10y_2y", "yield_curve_10y_3m", "credit_spread",
        "surprise_score", "spy_technicals",
    ]
    compact = {k: macro_context.get(k) for k in keys if macro_context.get(k)}
    upcoming = macro_context.get("upcoming_macro_events", []) or []
    compact["upcoming_top5"] = upcoming[:5]
    compact["regime"] = {
        "label": market_regime.regime,
        "sub": getattr(market_regime, "sub_regime", ""),
        "confidence": market_regime.confidence,
        "drivers": dict(market_regime.drivers or {}),
    }
    return compact


def _call_llm(payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from openai import OpenAI
    except Exception:
        return None

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    system = (
        "You are a macro strategist. Return valid JSON only matching this schema: "
        '{"headline": str, "three_themes": [str, str, str], "risk_map": str, '
        '"what_changed_this_week": str}. '
        "All fields must be in Korean, concise (each string <= 140 chars). "
        "Ground every claim in the provided numeric data."
    )
    user = (
        "다음 거시경제 스냅샷을 바탕으로 이번 주 시장 내러티브를 요약하세요.\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content if response.choices else None
    if not content:
        return None
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    # Normalize shape.
    out = {
        "headline": str(data.get("headline", "")).strip(),
        "three_themes": [str(t).strip() for t in (data.get("three_themes") or [])][:3],
        "risk_map": str(data.get("risk_map", "")).strip(),
        "what_changed_this_week": str(data.get("what_changed_this_week", "")).strip(),
    }
    if not out["headline"]:
        return None
    return out


def _fallback(market_regime: MarketRegime) -> dict[str, Any]:
    label = market_regime.regime or "neutral"
    sub = getattr(market_regime, "sub_regime", "") or ""
    drivers = market_regime.drivers or {}
    return {
        "headline": f"{label}" + (f" / {sub}" if sub else "") + " 레짐 유지",
        "three_themes": [
            str(drivers.get("trend", "SPY 추세 데이터 부족"))[:140],
            str(drivers.get("rates", "금리 데이터 부족"))[:140],
            str(drivers.get("vix", "VIX 데이터 부족"))[:140],
        ],
        "risk_map": market_regime.implication or "추가 데이터 확보 후 재평가 필요",
        "what_changed_this_week": "지난 영업일 대비 주요 드라이버 변화 요약 데이터 없음",
        "source": "fallback",
        "model": _MODEL,
    }


def _read_cache(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and data.get("headline"):
            return data
    except Exception:
        logger.debug("macro_narrative cache read failed: %s", path, exc_info=True)
    return None


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    except Exception:
        logger.debug("macro_narrative cache write failed: %s", path, exc_info=True)
