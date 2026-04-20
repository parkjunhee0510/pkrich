from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Callable

from src.collector import polygon_options as polygon_module
from src.collector.base import (
    CollectionContext,
    DataProvider,
    PartialTickerData,
    ProviderResult,
    RateLimit,
)
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)

_CACHE_TTL_HOURS = 24.0 * 14


class PolygonProvider(DataProvider):
    """Priority-2 Polygon options flow collector with cross-run enrichment."""

    name = "polygon"
    provides = {"options_flow", "options_summary"}
    priority = 2
    rate_limit = RateLimit(calls_per_minute=4, burst=1)

    def is_available(self) -> bool:
        try:
            return polygon_module.is_polygon_ready()
        except Exception:  # noqa: BLE001
            return False

    def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
        try:
            raw_snapshot = polygon_module.fetch_options_snapshot(ticker)
            if not raw_snapshot:
                return ProviderResult.failure(self.name, reason="no_options_data")

            flow = polygon_module.build_options_flow_from_snapshot(raw_snapshot)
            snapshot_metrics = polygon_module.extract_snapshot_metrics(raw_snapshot)
            if not flow and not snapshot_metrics:
                return ProviderResult.failure(self.name, reason="no_options_data")

            cache_set = _cache_setter(ctx)
            if cache_set is not None:
                cache_set(self.name, _snapshot_cache_key(ticker, ctx.run_date), snapshot_metrics, _CACHE_TTL_HOURS)

            previous_snapshot = _load_previous_snapshot_metrics(ticker, ctx)
            recent_pcr_values = _load_recent_pcr_values(snapshot_metrics, ticker, ctx)
            enriched_flow = _enrich_options_flow(flow, snapshot_metrics, previous_snapshot, recent_pcr_values)
            options_summary = _build_options_summary(enriched_flow)

            record_pipeline_event(
                "collector", "info", "data_provider_used",
                ticker=ticker, source=self.name,
            )
            return ProviderResult.success(
                self.name,
                PartialTickerData(
                    ticker=ticker,
                    fields={
                        "options_flow": enriched_flow,
                        "options_summary": options_summary,
                    },
                ),
            )
        except Exception as err:  # noqa: BLE001
            logger.exception("polygon provider failed for %s", ticker)
            record_pipeline_event(
                "collector", "warning", "ticker_provider_failed",
                ticker=ticker, source=self.name,
                error_type=type(err).__name__, error_message=str(err),
            )
            return ProviderResult.failure(self.name, reason=f"exception:{err}")


def _cache_getter(ctx: CollectionContext) -> Callable[[str, str], Any] | None:
    candidate = ctx.extra.get("cache_get")
    return candidate if callable(candidate) else None


def _cache_setter(ctx: CollectionContext) -> Callable[[str, str, Any, float], None] | None:
    candidate = ctx.extra.get("cache_set")
    return candidate if callable(candidate) else None


def _snapshot_cache_key(ticker: str, run_date) -> str:
    return f"{ticker}:options_snapshot:{run_date.isoformat()}"


def _load_previous_snapshot_metrics(ticker: str, ctx: CollectionContext) -> dict[str, Any] | None:
    cache_get = _cache_getter(ctx)
    if cache_get is None:
        return None
    previous_date = ctx.run_date - timedelta(days=1)
    entry = cache_get("polygon", _snapshot_cache_key(ticker, previous_date))
    if entry is None:
        return None
    payload = getattr(entry, "payload", None)
    return payload if isinstance(payload, dict) else None


def _load_recent_pcr_values(current_snapshot: dict[str, Any], ticker: str, ctx: CollectionContext) -> list[float]:
    values: list[float] = []
    current = _extract_pcr_value(current_snapshot)
    if current is not None:
        values.append(current)

    cache_get = _cache_getter(ctx)
    if cache_get is None:
        return values

    for offset in range(1, 8):
        if len(values) >= 3:
            break
        lookup_date = ctx.run_date - timedelta(days=offset)
        entry = cache_get("polygon", _snapshot_cache_key(ticker, lookup_date))
        if entry is None:
            continue
        payload = getattr(entry, "payload", None)
        if not isinstance(payload, dict):
            continue
        parsed = _extract_pcr_value(payload)
        if parsed is not None:
            values.append(parsed)

    return values


def _extract_pcr_value(snapshot_metrics: dict[str, Any]) -> float | None:
    for key in ("put_call_volume_ratio", "put_call_oi_ratio"):
        raw = str(snapshot_metrics.get(key, "")).strip()
        if not raw or raw == "N/A":
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _enrich_options_flow(
    flow: dict[str, str],
    current_snapshot: dict[str, Any],
    previous_snapshot: dict[str, Any] | None,
    recent_pcr_values: list[float],
) -> dict[str, str]:
    enriched = dict(flow)

    enriched["options_tone"] = _classify_options_tone(recent_pcr_values)
    enriched["pcr_trend_3d"] = _describe_pcr_trend(recent_pcr_values)

    put_change = _compute_oi_change_pct(current_snapshot, previous_snapshot, "total_put_oi")
    call_change = _compute_oi_change_pct(current_snapshot, previous_snapshot, "total_call_oi")
    enriched["put_oi_change_pct"] = put_change
    enriched["call_oi_change_pct"] = call_change
    enriched["net_oi_change_note"] = _build_oi_change_note(put_change, call_change)

    unusual_note = _build_unusual_activity_note(current_snapshot)
    enriched["unusual_activity_flag"] = "true" if unusual_note != "N/A" else "false"
    if unusual_note != "N/A":
        enriched["unusual_activity"] = unusual_note

    if "put_call_ratio" not in enriched:
        raw_ratio = current_snapshot.get("put_call_volume_ratio") or current_snapshot.get("put_call_oi_ratio") or "N/A"
        enriched["put_call_ratio"] = str(raw_ratio)

    return enriched


def _compute_oi_change_pct(current_snapshot: dict[str, Any], previous_snapshot: dict[str, Any] | None, key: str) -> str:
    if not previous_snapshot:
        return "N/A"
    current = _coerce_float(current_snapshot.get(key))
    previous = _coerce_float(previous_snapshot.get(key))
    if current is None or previous is None or previous <= 0:
        return "N/A"
    pct = ((current - previous) / previous) * 100
    return f"{pct:+.1f}%"


def _build_oi_change_note(put_change: str, call_change: str) -> str:
    if put_change == "N/A" and call_change == "N/A":
        return "N/A"
    return f"콜 OI {call_change} / 풋 OI {put_change}"


def _build_unusual_activity_note(snapshot_metrics: dict[str, Any]) -> str:
    unusual_contracts = snapshot_metrics.get("unusual_contracts", [])
    if not isinstance(unusual_contracts, list) or not unusual_contracts:
        return "N/A"

    parts: list[str] = []
    for contract in unusual_contracts[:3]:
        try:
            side = str(contract.get("side", "")).upper() or "N/A"
            strike = str(contract.get("strike", "N/A"))
            volume = int(contract.get("volume", 0))
            ratio = float(contract.get("vol_oi_ratio", 0.0)) * 100
        except (TypeError, ValueError):
            continue
        parts.append(f"{side} ${strike}, vol {volume}, OI 대비 {ratio:.0f}%")
    return " ; ".join(parts) if parts else "N/A"


def _classify_options_tone(values: list[float]) -> str:
    usable = values[:3]
    if len(usable) < 3:
        return "neutral"
    latest = usable[0]
    oldest = usable[-1]
    trend = latest - oldest
    if latest < 0.8 and trend < 0:
        return "bullish"
    if latest > 1.2 and trend > 0:
        return "bearish"
    return "neutral"


def _describe_pcr_trend(values: list[float]) -> str:
    usable = values[:3]
    if len(usable) < 3:
        return "insufficient_data"
    delta = usable[0] - usable[-1]
    if delta <= -0.1:
        return "falling"
    if delta >= 0.1:
        return "rising"
    return "stable"


def _build_options_summary(flow: dict[str, str]) -> dict[str, str]:
    summary: dict[str, str] = {}
    field_map = {
        "put_call_ratio": flow.get("put_call_ratio") or flow.get("put_call_volume_ratio") or flow.get("put_call_oi_ratio"),
        "tone": flow.get("options_tone", "neutral"),
        "unusual_activity": flow.get("unusual_activity", "N/A"),
        "oi_change": flow.get("net_oi_change_note", "N/A"),
    }
    for key, value in field_map.items():
        if value not in (None, ""):
            summary[key] = str(value)
    return summary


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["PolygonProvider"]
