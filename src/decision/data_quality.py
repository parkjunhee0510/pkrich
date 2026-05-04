from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from src.types import CollectedTickerData, TickerAnalysis


@dataclass(frozen=True)
class DataQualityResult:
    score: float
    components: dict[str, float]
    confidence_penalty: float

    def to_meta(self) -> dict[str, object]:
        return {
            "data_quality": self.score,
            "data_quality_score": self.score,
            "data_quality_components": dict(self.components),
            "confidence_penalty": self.confidence_penalty,
        }


def calculate_data_quality_result(
    *,
    analysis: TickerAnalysis,
    data: CollectedTickerData | None,
    run_date: date | None,
    quality_summary: dict[str, Any] | None,
    macro_context: dict[str, Any] | None,
) -> DataQualityResult:
    quality_summary = quality_summary or {}
    components = {
        "analyzer_validation": _analyzer_validation_score(analysis, quality_summary),
        "price_freshness": _price_freshness_score(analysis, data, run_date),
        "news_coverage": _news_coverage_score(analysis),
        "missing_fundamentals": _fundamentals_score(analysis, data),
        "source_diversity": _source_diversity_score(analysis),
        "fallback_depth": _fallback_depth_score(data, quality_summary),
        "macro_context_age": _macro_context_score(macro_context),
    }
    score = _clamp(
        0.25 * components["analyzer_validation"]
        + 0.20 * components["price_freshness"]
        + 0.15 * components["news_coverage"]
        + 0.15 * components["missing_fundamentals"]
        + 0.10 * components["source_diversity"]
        + 0.10 * components["fallback_depth"]
        + 0.05 * components["macro_context_age"]
    )
    return DataQualityResult(
        score=score,
        components={key: _clamp(value) for key, value in components.items()},
        confidence_penalty=_clamp(1.0 - score),
    )


def _analyzer_validation_score(analysis: TickerAnalysis, quality_summary: dict[str, Any]) -> float:
    critical_total = _to_int(quality_summary.get("critical_field_total"))
    missing_critical = _to_int(quality_summary.get("missing_critical_fields"))
    if critical_total > 0:
        missing_ratio = min(1.0, missing_critical / critical_total)
    else:
        fields = [
            analysis.summary,
            analysis.signal_or_takeaway,
            analysis.data_snapshot.get("Price", ""),
            analysis.data_snapshot.get("Sector", ""),
            analysis.key_news[0] if analysis.key_news else "",
            analysis.financial_highlights[0] if analysis.financial_highlights else "",
        ]
        missing_ratio = sum(1 for value in fields if _is_missing(value)) / len(fields)

    score = 1.0 - 0.30 * missing_ratio
    score -= 0.08 * min(3, _to_int(quality_summary.get("fact_warning_count")))
    score -= 0.08 * min(3, _to_int(quality_summary.get("consistency_warning_count")))
    score -= 0.18 * min(2, _to_int(quality_summary.get("hallucination_warning_count")))
    if bool(quality_summary.get("fallback_used", False)):
        score -= 0.08
    if bool(quality_summary.get("encoding_issue_detected", False)):
        score -= 0.12
    return _clamp(score)


def _price_freshness_score(
    analysis: TickerAnalysis,
    data: CollectedTickerData | None,
    run_date: date | None,
) -> float:
    if run_date is None:
        return 0.75 if data is not None and data.price is not None else 0.4
    latest = _latest_price_date((data.historical_prices if data else []) or analysis.historical_prices)
    if latest is None:
        return 0.75 if data is not None and data.price is not None else 0.35
    age_days = max((run_date - latest).days, 0)
    if age_days <= 1:
        return 1.0
    if age_days <= 3:
        return 0.85
    if age_days <= 7:
        return 0.65
    if age_days <= 14:
        return 0.45
    return 0.25


def _news_coverage_score(analysis: TickerAnalysis) -> float:
    count = len(analysis.news_references) or len(analysis.key_news)
    if count >= 3:
        return 1.0
    if count == 2:
        return 0.8
    if count == 1:
        return 0.55
    return 0.25


def _source_diversity_score(analysis: TickerAnalysis) -> float:
    sources = {
        str(item.source or "").strip().lower()
        for item in analysis.news_references
        if str(item.source or "").strip()
    }
    if len(sources) >= 3:
        return 1.0
    if len(sources) == 2:
        return 0.8
    if len(sources) == 1:
        return 0.5
    return 0.35


def _fundamentals_score(analysis: TickerAnalysis, data: CollectedTickerData | None) -> float:
    values = [
        analysis.fundamentals.get("pe_ratio"),
        analysis.fundamentals.get("eps"),
        analysis.fundamentals.get("market_cap"),
        getattr(data, "pe_ratio", "N/A") if data else "N/A",
        getattr(data, "eps", "N/A") if data else "N/A",
        getattr(data, "market_cap", "N/A") if data else "N/A",
    ]
    present = sum(1 for value in values if not _is_missing(value))
    return _clamp(present / len(values))


def _fallback_depth_score(data: CollectedTickerData | None, quality_summary: dict[str, Any]) -> float:
    if bool(quality_summary.get("fallback_used", False)):
        return 0.55
    note = str(getattr(data, "summary_note", "") if data else "").lower()
    if "불러오지 못해" in note or "fallback" in note or "기본값" in note:
        return 0.45
    if "stooq" in note or "alpha" in note:
        return 0.75
    return 1.0


def _macro_context_score(macro_context: dict[str, Any] | None) -> float:
    macro_context = macro_context or {}
    if not macro_context:
        return 0.5
    useful_keys = ("macro_events", "market_regime", "vix", "rates", "macro_narrative")
    present = sum(1 for key in useful_keys if macro_context.get(key))
    return _clamp(0.55 + 0.45 * (present / len(useful_keys)))


def _latest_price_date(rows: list[dict[str, Any]]) -> date | None:
    latest: date | None = None
    for row in rows:
        try:
            parsed = date.fromisoformat(str(row.get("date", "")))
        except ValueError:
            continue
        if latest is None or parsed > latest:
            latest = parsed
    return latest


def _is_missing(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"", "n/a", "na", "none", "unknown", "null"}


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, round(float(value), 4)))
