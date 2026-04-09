from __future__ import annotations

import re
from typing import Mapping

_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")
_DAY_PATTERN = re.compile(r"D-(\d+)(?:\s*[·|]\s*([A-Z]+))?")


def build_earnings_setup(
    fundamentals: Mapping[str, str],
    quarterly_rows: list[dict[str, str]],
    upcoming_events: list[dict[str, str]],
    *,
    currency: str = "USD",
) -> dict[str, str]:
    latest_row = _latest_consensus_row(quarterly_rows)
    ttm_eps = _append_unit(fundamentals.get("eps", "N/A"), f"{currency}/share")
    forward_eps = _append_unit(fundamentals.get("forward_eps", "N/A"), f"{currency}/share")

    return {
        "forward_eps": forward_eps,
        "ttm_eps": ttm_eps,
        "forward_vs_ttm": _format_forward_vs_ttm(fundamentals.get("forward_eps"), fundamentals.get("eps")),
        "earnings_growth": _normalize_growth(fundamentals.get("earnings_growth", "N/A")),
        "latest_estimated_eps": _append_unit(latest_row.get("estimated_eps", "N/A"), f"{currency}/share"),
        "latest_surprise_pct": latest_row.get("surprise_pct", "N/A"),
        "latest_beat_miss": latest_row.get("beat_miss", "N/A"),
        "next_earnings_event": _next_earnings_event(upcoming_events),
    }


def extract_earnings_countdown(value: str | None) -> str:
    text = str(value or "").strip()
    if not text or text == "N/A":
        return "N/A"
    match = _DAY_PATTERN.search(text)
    if not match:
        return "N/A"
    days = match.group(1)
    timing = (match.group(2) or "").strip()
    return f"D-{days} · {timing}" if timing else f"D-{days}"


def _latest_consensus_row(rows: list[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        estimated_eps = str(row.get("estimated_eps", "N/A")).strip()
        surprise_pct = str(row.get("surprise_pct", "N/A")).strip()
        if estimated_eps not in {"", "N/A"} or surprise_pct not in {"", "N/A"}:
            return row
    return {}


def _format_forward_vs_ttm(forward_eps: str | None, ttm_eps: str | None) -> str:
    forward_value = _parse_numeric(forward_eps)
    ttm_value = _parse_numeric(ttm_eps)
    if forward_value is None or ttm_value is None or ttm_value == 0:
        return "N/A"
    delta = ((forward_value - ttm_value) / abs(ttm_value)) * 100
    return f"{delta:+.2f}%"


def _normalize_growth(value: str | None) -> str:
    text = str(value or "").strip()
    if not text or text == "N/A":
        return "N/A"
    return text if any(token in text for token in ("YoY", "est", "FY")) else f"{text} YoY"


def _next_earnings_event(events: list[dict[str, str]]) -> str:
    for event in events:
        if str(event.get("type", "")).strip() != "earnings":
            continue
        event_date = str(event.get("date", "N/A")).strip() or "N/A"
        days_until = str(event.get("days_until", "N/A")).strip() or "N/A"
        timing = str(event.get("timing", "")).strip()
        label = str(event.get("label", "실적 발표")).strip() or "실적 발표"
        suffix = f"D-{days_until}"
        if timing:
            suffix = f"{suffix} · {timing}"
        return f"{event_date} {label} ({suffix})"
    return "N/A"


def _append_unit(value: str | None, unit: str) -> str:
    text = str(value or "").strip()
    if not text or text == "N/A":
        return "N/A"
    return text if text.endswith(unit) else f"{text} {unit}".strip()


def _parse_numeric(value: str | None) -> float | None:
    text = str(value or "").strip()
    if not text or text == "N/A":
        return None
    match = _NUMBER_PATTERN.search(text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None
