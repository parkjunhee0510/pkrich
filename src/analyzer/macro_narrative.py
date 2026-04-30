"""Run-level macro narrative synthesis.

Calls the LLM once per run to produce a compact, structured macro narrative
that is injected into every ticker prompt. Output is cached per run_date for
24 hours to cap cost at one call per run.

Upgraded to use the OpenAI Responses API with the ``web_search`` tool so the
narrative is grounded in real macro headlines (Fed minutes, CPI prints, ECB
guidance, geopolitics) instead of being projected from VIX/yields alone.
The numeric snapshot still flows in as input so the LLM cross-references the
news with the data.

Fails soft: returns an empty dict on any error so prompt assembly degrades
gracefully to the raw macro context.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

from src.types import MarketRegime

logger = logging.getLogger(__name__)

_CACHE_DIR = Path("output/cache")
# Default model = gpt-5.4 family (Responses API web_search supported). Override
# via env if needed; o3-mini does NOT reliably support web_search.
_MODEL = os.getenv("PKRICH_MACRO_NARRATIVE_MODEL", "gpt-5.4")
_FLAG = "PKRICH_MACRO_NARRATIVE"
# Bump when output schema changes — old cached files are treated as miss.
_SCHEMA_VERSION = 2
_CACHE_TTL_SECONDS = 24 * 60 * 60


def build_macro_narrative(
    macro_context: dict[str, Any],
    market_regime: MarketRegime,
    run_date: date,
) -> dict[str, Any]:
    """Return cached or freshly-generated narrative for ``run_date``.

    Structure::

        {
          "schema_version": 2,
          "headline": "...",
          "three_themes": ["...", "...", "..."],
          "risk_map": "short sentence",
          "what_changed_this_week": "short sentence",
          "key_headlines": [
            {"title": "...", "source": "Reuters", "url": "https://...",
             "takeaway": "한국어 1문장"},
            ... up to 5
          ],
          "source": "llm" | "fallback",
          "model": "gpt-5.4"
        }
    """
    if os.getenv(_FLAG, "1") == "0":
        return _fallback(market_regime)

    cache_path = _CACHE_DIR / f"macro_narrative_{run_date.isoformat()}.json"
    cached = _read_cache(cache_path)
    if cached and not _should_refresh_cache(cache_path, cached, market_regime):
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
        narrative.setdefault("schema_version", _SCHEMA_VERSION)

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
    """Run web_search-augmented synthesis via the Responses API."""
    try:
        from openai import OpenAI
    except Exception:
        return None

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    headline_item_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "source": {"type": "string"},
            "url": {"type": "string"},
            "takeaway": {"type": "string"},
        },
        "required": ["title", "source", "url", "takeaway"],
        "additionalProperties": False,
    }
    schema = {
        "type": "object",
        "properties": {
            "headline": {"type": "string"},
            "three_themes": {
                "type": "array",
                "items": {"type": "string"},
            },
            "risk_map": {"type": "string"},
            "what_changed_this_week": {"type": "string"},
            "key_headlines": {
                "type": "array",
                "items": headline_item_schema,
            },
        },
        "required": [
            "headline",
            "three_themes",
            "risk_map",
            "what_changed_this_week",
            "key_headlines",
        ],
        "additionalProperties": False,
    }

    instructions = (
        "You are a macro strategist for a Korean retail trading dashboard. "
        "Use the web_search tool to find the most relevant US/global macro "
        "news from the last 7 days (Fed/FOMC, CPI/PCE/PPI/NFP/ISM, ECB, "
        "China data, geopolitics, oil shocks). Cross-reference your findings "
        "with the provided numeric snapshot. Always cite at least 3 and at "
        "most 5 headlines in key_headlines with real source URLs. "
        "Every text field must be in Korean. headline ≤ 80 chars. "
        "Each three_themes item ≤ 140 chars. risk_map ≤ 140 chars. "
        "what_changed_this_week ≤ 140 chars. takeaway is a 1-sentence "
        "Korean summary ≤ 100 chars. Always return exactly 3 three_themes."
    )
    user_msg = (
        "거시경제 스냅샷:\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\n위 정량 데이터와 web_search로 찾은 최신 뉴스를 종합해 한국어 brief을 작성하라."
    )

    response = client.responses.create(
        model=_MODEL,
        tools=[{"type": "web_search"}],
        input=user_msg,
        instructions=instructions,
        text={
            "format": {
                "type": "json_schema",
                "name": "macro_narrative",
                "schema": schema,
                "strict": True,
            },
        },
    )

    try:
        data = json.loads(response.output_text)
    except (AttributeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    # Normalize shape.
    headlines_raw = data.get("key_headlines") or []
    headlines: list[dict[str, str]] = []
    for h in headlines_raw[:5]:
        if not isinstance(h, dict):
            continue
        title = str(h.get("title", "")).strip()
        url = str(h.get("url", "")).strip()
        if not title or not url:
            continue
        headlines.append({
            "title": title[:200],
            "source": str(h.get("source", "")).strip()[:80],
            "url": url[:500],
            "takeaway": str(h.get("takeaway", "")).strip()[:200],
        })

    out = {
        "schema_version": _SCHEMA_VERSION,
        "headline": str(data.get("headline", "")).strip(),
        "three_themes": [
            str(t).strip() for t in (data.get("three_themes") or [])
        ][:3],
        "risk_map": str(data.get("risk_map", "")).strip(),
        "what_changed_this_week": str(data.get("what_changed_this_week", "")).strip(),
        "key_headlines": headlines,
    }
    if not out["headline"]:
        return None
    return out


def _fallback(market_regime: MarketRegime) -> dict[str, Any]:
    label = market_regime.regime or "neutral"
    sub = getattr(market_regime, "sub_regime", "") or ""
    drivers = market_regime.drivers or {}
    return {
        "schema_version": _SCHEMA_VERSION,
        "headline": f"{label}" + (f" / {sub}" if sub else "") + " 레짐 유지",
        "three_themes": [
            str(drivers.get("trend", "SPY 추세 데이터 부족"))[:140],
            str(drivers.get("rates", "금리 데이터 부족"))[:140],
            str(drivers.get("vix", "VIX 데이터 부족"))[:140],
        ],
        "risk_map": market_regime.implication or "추가 데이터 확보 후 재평가 필요",
        "what_changed_this_week": "지난 영업일 대비 주요 드라이버 변화 요약 데이터 없음",
        "key_headlines": [],
        "source": "fallback",
        "model": _MODEL,
    }


def _read_cache(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not (isinstance(data, dict) and data.get("headline")):
            return None
        # Force-refresh on schema upgrade so old cached entries (no
        # key_headlines) don't sneak past the new code path.
        if data.get("schema_version") != _SCHEMA_VERSION:
            return None
        return data
    except Exception:
        logger.debug("macro_narrative cache read failed: %s", path, exc_info=True)
    return None


def _should_refresh_cache(path: Path, cached: dict[str, Any], market_regime: MarketRegime) -> bool:
    return _cache_is_expired(path) or _cached_fallback_has_missing_driver_evidence(cached, market_regime)


def _cache_is_expired(path: Path) -> bool:
    try:
        return time.time() - path.stat().st_mtime > _CACHE_TTL_SECONDS
    except OSError:
        return True


def _cached_fallback_has_missing_driver_evidence(
    cached: dict[str, Any],
    market_regime: MarketRegime,
) -> bool:
    if cached.get("source") != "fallback":
        return False

    themes = cached.get("three_themes")
    if not isinstance(themes, list):
        return False
    if not any(_contains_missing_marker(theme) for theme in themes):
        return False

    drivers = market_regime.drivers or {}
    return any(
        isinstance(value := drivers.get(key), str)
        and value.strip()
        and not _contains_missing_marker(value)
        for key in ("trend", "rates", "vix")
    )


def _contains_missing_marker(value: Any) -> bool:
    return "N/A" in str(value)


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    except Exception:
        logger.debug("macro_narrative cache write failed: %s", path, exc_info=True)
