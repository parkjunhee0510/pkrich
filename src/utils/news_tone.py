from __future__ import annotations

from src.types import NewsItem, TickerAnalysis

_POSITIVE_TERMS = {
    "beat": 2,
    "strong": 1,
    "growth": 1,
    "upgrade": 2,
    "upside": 1,
    "record": 1,
    "surge": 2,
    "rebound": 1,
    "partnership": 1,
    "launch": 1,
    "demand": 1,
    "guidance raised": 2,
    "호조": 2,
    "상향": 2,
    "성장": 1,
    "강세": 1,
}
_NEGATIVE_TERMS = {
    "miss": -2,
    "weak": -1,
    "downgrade": -2,
    "cut": -1,
    "decline": -1,
    "delay": -1,
    "lawsuit": -2,
    "probe": -2,
    "slump": -2,
    "headwind": -1,
    "warning": -1,
    "guidance cut": -2,
    "부진": -2,
    "하향": -2,
    "약세": -1,
    "소송": -2,
    "지연": -1,
}


def build_news_tone(analysis: TickerAnalysis) -> dict[str, str | float]:
    text_parts: list[str] = []
    text_parts.extend(summary for summary in analysis.key_news if summary)
    text_parts.extend(item.title for item in analysis.news_references if isinstance(item, NewsItem) and item.title)
    normalized_text = " ".join(text_parts).lower()

    if not normalized_text or _only_fallback_news(analysis.news_references):
        return {"label": "neutral", "score": 0.0}

    score = 0.0
    for term, value in _POSITIVE_TERMS.items():
        if term in normalized_text:
            score += value
    for term, value in _NEGATIVE_TERMS.items():
        if term in normalized_text:
            score += value

    if score >= 2:
        label = "bullish"
    elif score <= -2:
        label = "bearish"
    else:
        label = "neutral"

    return {"label": label, "score": float(score)}


def _only_fallback_news(items: list[NewsItem]) -> bool:
    visible = [item for item in items if item.title]
    if not visible:
        return True
    return all((item.source or "").strip().lower() == "fallback" for item in visible)
