from __future__ import annotations

from typing import Any

from src.analyzer import research_note


def build_peer_rank(
    *,
    company_metrics: dict[str, str],
    peer_metrics: list[dict[str, str]],
) -> dict[str, object]:
    metrics = {
        "per_pctl": _percentile(
            company_metrics.get("pe_ratio"),
            [peer.get("pe_ratio", "N/A") for peer in peer_metrics],
            lower_is_better=True,
        ),
        "rs_pctl": _percentile(
            company_metrics.get("price_change_30d"),
            [peer.get("price_change_30d", "N/A") for peer in peer_metrics],
            lower_is_better=False,
        ),
        "roe_pctl": _percentile(
            company_metrics.get("roe"),
            [peer.get("roe", "N/A") for peer in peer_metrics],
            lower_is_better=False,
        ),
        "revenue_growth_pctl": _percentile(
            company_metrics.get("revenue_growth"),
            [peer.get("revenue_growth", "N/A") for peer in peer_metrics],
            lower_is_better=False,
        ),
        "dividend_yield_pctl": _percentile(
            company_metrics.get("dividend_yield"),
            [peer.get("dividend_yield", "N/A") for peer in peer_metrics],
            lower_is_better=False,
        ),
    }
    summary = _build_summary(metrics)
    payload = {key: value for key, value in metrics.items() if value != "N/A"}
    if summary:
        payload["summary"] = summary
    return payload


def _percentile(
    company_value: Any,
    peer_values: list[Any],
    *,
    lower_is_better: bool,
) -> int | str:
    company_numeric = _parse_numeric(company_value)
    if company_numeric is None:
        return "N/A"

    usable = [value for value in (_parse_numeric(item) for item in peer_values) if value is not None]
    universe = usable + [company_numeric]
    if len(universe) < 3:
        return "N/A"

    if lower_is_better:
        wins = sum(1 for value in universe if value > company_numeric)
    else:
        wins = sum(1 for value in universe if value < company_numeric)

    percentile = round((wins / len(universe)) * 100)
    return max(0, min(100, percentile))


def _build_summary(metrics: dict[str, int | str]) -> str:
    parts: list[str] = []

    per_pctl = metrics.get("per_pctl")
    if isinstance(per_pctl, int):
        if per_pctl <= 30:
            parts.append(f"PER 하위 {per_pctl}% (저평가)")
        elif per_pctl >= 70:
            parts.append(f"PER 상위 {100 - per_pctl}% (고평가)")

    rs_pctl = metrics.get("rs_pctl")
    if isinstance(rs_pctl, int):
        if rs_pctl >= 70:
            parts.append(f"모멘텀 상위 {100 - rs_pctl}%")
        elif rs_pctl <= 30:
            parts.append(f"모멘텀 하위 {rs_pctl}%")

    roe_pctl = metrics.get("roe_pctl")
    if isinstance(roe_pctl, int) and not parts:
        if roe_pctl >= 70:
            parts.append(f"ROE 상위 {100 - roe_pctl}%")
        elif 40 <= roe_pctl <= 60:
            parts.append("ROE 중간")

    return ", ".join(parts[:3])


def _parse_numeric(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text == "N/A":
        return None
    cleaned = text.replace(",", "").replace("%", "").replace("x", "").replace("X", "").split()[0]
    return research_note._parse_float_from_text(cleaned)
