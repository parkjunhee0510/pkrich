from __future__ import annotations

import re
from typing import Any


_NUMBER_TOKEN = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def compute_signal_must_use_values(
    raw_payload: dict[str, Any],
    trade_frame: dict[str, Any] | None,
) -> dict[str, Any]:
    current_price = _to_float(raw_payload.get("price"))
    atr_14 = _to_float((raw_payload.get("price_action") or {}).get("atr_14d"))
    if atr_14 is None:
        atr_14 = _to_float(raw_payload.get("atr_14d"))

    support_levels = _dedupe_levels(
        [
            _to_float((trade_frame or {}).get("stop_loss")),
            _to_float((trade_frame or {}).get("invalidation_price")),
            _to_float((trade_frame or {}).get("entry_price")),
            _to_float(raw_payload.get("sma_50")),
            _to_float(raw_payload.get("sma_200")),
            _to_float(raw_payload.get("week52_low")),
        ],
        current_price=current_price,
        side="support",
    )
    resistance_levels = _dedupe_levels(
        [
            _to_float((trade_frame or {}).get("target_1")),
            _to_float((trade_frame or {}).get("target_2")),
            _to_float((raw_payload.get("positioning") or {}).get("analyst_target_price")),
            _to_float(raw_payload.get("week52_high")),
            _to_float(raw_payload.get("sma_50")),
            _to_float(raw_payload.get("sma_200")),
        ],
        current_price=current_price,
        side="resistance",
    )

    next_earnings = "N/A"
    for event in raw_payload.get("upcoming_events", []) or []:
        if str(event.get("type", "")).strip().lower() == "earnings":
            next_earnings = str(event.get("date", "")).strip() or "N/A"
            break

    return {
        "current_price": _format_level(current_price),
        "atr_14": _format_level(atr_14),
        "support_levels": [_format_level(level) for level in support_levels],
        "resistance_levels": [_format_level(level) for level in resistance_levels],
        "next_earnings": next_earnings,
    }


def allowed_signal_levels(
    raw_payload: dict[str, Any],
    trade_frame: dict[str, Any] | None,
    direction: str | None = None,
) -> dict[str, list[float]]:
    must_use = compute_signal_must_use_values(raw_payload, trade_frame)
    supports = [_to_float(item) for item in must_use.get("support_levels", [])]
    resistances = [_to_float(item) for item in must_use.get("resistance_levels", [])]
    support_levels = [item for item in supports if item is not None]
    resistance_levels = [item for item in resistances if item is not None]
    if direction == "long":
        return {"targets": resistance_levels, "stop": support_levels}
    if direction == "short":
        return {"targets": support_levels, "stop": resistance_levels}
    return {"targets": resistance_levels + support_levels, "stop": support_levels + resistance_levels}


def _dedupe_levels(
    levels: list[float | None],
    *,
    current_price: float | None,
    side: str,
) -> list[float]:
    filtered: list[float] = []
    for level in levels:
        if level is None or level <= 0:
            continue
        if current_price is not None:
            if side == "support" and level > current_price * 1.01:
                continue
            if side == "resistance" and level < current_price * 0.99:
                continue
        if any(abs(level - known) <= max(abs(known), 1.0) * 0.002 for known in filtered):
            continue
        filtered.append(level)
    reverse = side == "support"
    return sorted(filtered, reverse=reverse)[:4]


def _format_level(value: float | None) -> str:
    if value is None or value <= 0:
        return "N/A"
    return f"{value:.2f}"


def _to_float(raw: Any) -> float | None:
    try:
        if raw is None:
            return None
        normalized = str(raw).replace(",", "").strip()
        if not normalized:
            return None
        match = _NUMBER_TOKEN.search(normalized)
        if not match:
            return None
        number = float(match.group(0))
        if number.is_integer() and 1900 <= number <= 2100:
            return None
        return number
    except (TypeError, ValueError):
        return None
