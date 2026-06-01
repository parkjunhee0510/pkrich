from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from urllib.parse import quote_plus

from src.collector.feed_fetch import parse_feed
from src.types import NewsItem
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

try:
    import certifi  # type: ignore
except Exception:  # pragma: no cover
    certifi = None  # type: ignore


@dataclass(frozen=True)
class MacroShockRule:
    event_type: str
    region: str
    severity: str
    transmission_channels: tuple[str, ...]
    affected_sectors: tuple[str, ...]
    affected_industries: tuple[str, ...]
    direction: str
    expires_in_days: int
    any_keywords: tuple[str, ...]
    # Synonym group: an event matches when it contains a primary `any_keywords`
    # term AND (if set) ANY ONE of these qualifiers. These are alternatives, not
    # a conjunction — do not change the matching logic to require all of them.
    qualifier_keywords: tuple[str, ...] = ()


_RSS_PROVIDERS = (
    {"name": "Reuters", "site_filter": "reuters.com"},
    {"name": "Associated Press", "site_filter": "apnews.com"},
    {"name": "CNBC", "site_filter": "cnbc.com"},
    {"name": "Yahoo Finance", "site_filter": "finance.yahoo.com"},
)

_SEARCH_QUERIES = (
    "Strait of Hormuz closure oil shipping",
    "Middle East escalation oil supply shipping",
    "OPEC production cut supply shock",
    "global shipping disruption Red Sea freight",
    "sanctions export control supply chain",
)

_RULES: tuple[MacroShockRule, ...] = (
    MacroShockRule(
        event_type="hormuz_disruption",
        region="middle_east",
        severity="high",
        transmission_channels=("oil", "shipping", "risk_sentiment"),
        affected_sectors=("Energy", "Industrials", "Consumer Cyclical", "Technology"),
        affected_industries=("Airlines", "Shipping", "Oil & Gas", "Defense"),
        direction="mixed",
        expires_in_days=7,
        any_keywords=("strait of hormuz", "hormuz"),
        qualifier_keywords=("close", "closure", "block", "blockade", "shut"),
    ),
    MacroShockRule(
        event_type="middle_east_escalation",
        region="middle_east",
        severity="high",
        transmission_channels=("oil", "risk_sentiment", "shipping"),
        affected_sectors=("Energy", "Industrials", "Consumer Cyclical", "Technology", "Utilities"),
        affected_industries=("Defense", "Airlines", "Shipping", "Oil & Gas"),
        direction="risk_off",
        expires_in_days=5,
        any_keywords=("iran", "israel", "middle east", "tehran", "gaza", "red sea"),
        qualifier_keywords=("strike", "attack", "missile", "escalat", "retaliat", "conflict", "war"),
    ),
    MacroShockRule(
        event_type="opec_supply_shock",
        region="global",
        severity="high",
        transmission_channels=("oil", "inflation", "risk_sentiment"),
        affected_sectors=("Energy", "Consumer Cyclical", "Industrials", "Utilities"),
        affected_industries=("Airlines", "Trucking", "Oil & Gas"),
        direction="mixed",
        expires_in_days=10,
        any_keywords=("opec", "opec+"),
        qualifier_keywords=("cut", "output", "production", "supply"),
    ),
    MacroShockRule(
        event_type="shipping_disruption",
        region="global",
        severity="medium",
        transmission_channels=("shipping", "supply_chain", "risk_sentiment"),
        affected_sectors=("Industrials", "Consumer Cyclical", "Technology", "Materials"),
        affected_industries=("Shipping", "Logistics", "Semiconductors", "Consumer Electronics"),
        direction="risk_off",
        expires_in_days=7,
        any_keywords=("red sea", "shipping", "container", "freight", "suez", "port strike"),
        qualifier_keywords=("disrupt", "halt", "delay", "surge", "reroute", "attack"),
    ),
    MacroShockRule(
        event_type="sanctions_escalation",
        region="global",
        severity="medium",
        transmission_channels=("supply_chain", "rates", "risk_sentiment"),
        affected_sectors=("Technology", "Industrials", "Materials", "Financial"),
        affected_industries=("Semiconductors", "Electronics", "Defense", "Shipping"),
        direction="risk_off",
        expires_in_days=14,
        any_keywords=("sanction", "embargo", "tariff", "export control", "blacklist"),
    ),
)

_SEVERITY_SCORE = {"high": 3, "medium": 2, "low": 1}


def collect_macro_shock_events(run_date: date, *, max_items: int = 3) -> list[dict[str, Any]]:
    if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
        return []

    candidates = _collect_macro_shock_news(run_date)
    classified = [
        event
        for item in candidates
        if (event := _classify_macro_shock_event(item, run_date)) is not None
    ]
    merged = _merge_macro_shock_events(classified)
    return merged[:max_items]


def _collect_macro_shock_news(run_date: date) -> list[NewsItem]:
    items: list[NewsItem] = []
    if can_open_tcp_connection("news.google.com", 443):
        for query in _SEARCH_QUERIES:
            for provider in _RSS_PROVIDERS:
                items.extend(_collect_google_news(query, provider))
    if can_open_tcp_connection("duckduckgo.com", 443):
        for query in _SEARCH_QUERIES:
            items.extend(_search_duckduckgo(query))

    filtered = [item for item in items if _is_recent(item, run_date)]
    filtered.sort(key=_macro_news_rank_key, reverse=True)
    return filtered


def _collect_google_news(query: str, provider: dict[str, str]) -> list[NewsItem]:
    try:
        import feedparser  # type: ignore
    except Exception:
        return []

    try:
        query_with_site = query
        site_filter = provider.get("site_filter", "").strip()
        if site_filter:
            query_with_site = f"{query} site:{site_filter}"
        feed = parse_feed(f"https://news.google.com/rss/search?q={quote_plus(query_with_site)}")
        items: list[NewsItem] = []
        for entry in feed.entries[:4]:
            title = str(getattr(entry, "title", "")).strip()
            if not title:
                continue
            source_title = provider["name"]
            if hasattr(entry, "source"):
                source_title = str(getattr(entry, "source", {}).get("title", provider["name"])) or provider["name"]
            items.append(
                NewsItem(
                    title=title,
                    source=source_title,
                    published_at=str(getattr(entry, "published", "")),
                    link=str(getattr(entry, "link", "")),
                )
            )
        return items
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "macro_event_provider_failed",
            source=provider.get("name", "Google News"),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return []


def _search_duckduckgo(query: str, *, max_results: int = 4) -> list[NewsItem]:
    try:
        from ddgs import DDGS  # type: ignore
    except Exception:
        return []

    try:
        ddgs = DDGS(verify=_ddgs_verify_setting())
        rows = ddgs.text(query, region="wt-wt", safesearch="moderate", max_results=max_results)
        items: list[NewsItem] = []
        for row in rows or []:
            title = str(row.get("title", "")).strip()
            if not title:
                continue
            items.append(
                NewsItem(
                    title=title,
                    source=str(row.get("source", "DuckDuckGo")).strip() or "DuckDuckGo",
                    published_at=str(row.get("date", "")).strip(),
                    link=str(row.get("href", "")).strip(),
                )
            )
        return items
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "macro_event_provider_failed",
            source="DuckDuckGo",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return []


def _classify_macro_shock_event(item: NewsItem, run_date: date) -> dict[str, Any] | None:
    text = f"{item.title} {item.source}".strip().lower()
    for rule in _RULES:
        if not any(keyword in text for keyword in rule.any_keywords):
            continue
        if rule.qualifier_keywords and not any(keyword in text for keyword in rule.qualifier_keywords):
            continue
        summary = _build_summary(rule)
        return {
            "event_type": rule.event_type,
            "severity": rule.severity,
            "region": rule.region,
            "transmission_channels": list(rule.transmission_channels),
            "affected_sectors": list(rule.affected_sectors),
            "affected_industries": list(rule.affected_industries),
            "direction": rule.direction,
            "summary_ko": summary,
            "expires_at": (run_date + timedelta(days=rule.expires_in_days)).isoformat(),
            "headline": item.title,
            "source": item.source,
            "published_at": item.published_at,
            "link": item.link,
        }
    return None


def _merge_macro_shock_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged_by_type: dict[str, dict[str, Any]] = {}
    for event in events:
        event_type = str(event.get("event_type", "")).strip()
        if not event_type:
            continue
        current = merged_by_type.get(event_type)
        if current is None:
            merged_by_type[event_type] = dict(event)
            continue
        current_score = _SEVERITY_SCORE.get(str(current.get("severity", "low")), 1)
        new_score = _SEVERITY_SCORE.get(str(event.get("severity", "low")), 1)
        if new_score > current_score:
            current.update({key: value for key, value in event.items() if key != "headline"})
        current_headline = str(current.get("headline", "")).strip()
        incoming_headline = str(event.get("headline", "")).strip()
        if incoming_headline and incoming_headline not in current_headline:
            current["headline"] = current_headline or incoming_headline

    merged = list(merged_by_type.values())
    merged.sort(
        key=lambda event: (
            _SEVERITY_SCORE.get(str(event.get("severity", "low")), 1),
            str(event.get("published_at", "")),
        ),
        reverse=True,
    )
    return [
        {
            "event_type": str(event.get("event_type", "")),
            "severity": str(event.get("severity", "medium")),
            "region": str(event.get("region", "global")),
            "transmission_channels": list(event.get("transmission_channels", [])),
            "affected_sectors": list(event.get("affected_sectors", [])),
            "affected_industries": list(event.get("affected_industries", [])),
            "direction": str(event.get("direction", "mixed")),
            "summary_ko": str(event.get("summary_ko", "")).strip(),
            "expires_at": str(event.get("expires_at", "")),
        }
        for event in merged
    ]


def _build_summary(rule: MacroShockRule) -> str:
    if rule.event_type == "hormuz_disruption":
        return "호르무즈 해협 차질로 유가와 해상 물류 변동성이 동시에 커질 수 있습니다."
    if rule.event_type == "middle_east_escalation":
        return "중동 확전 우려로 위험자산 선호가 약해지고 에너지 가격 민감도가 높아질 수 있습니다."
    if rule.event_type == "opec_supply_shock":
        return "OPEC 공급 충격은 에너지 가격과 기대 인플레이션을 다시 자극할 수 있습니다."
    if rule.event_type == "shipping_disruption":
        return "글로벌 해운 차질은 운송비와 재고 리스크를 높여 공급망 민감 업종에 부담입니다."
    if rule.event_type == "sanctions_escalation":
        return "제재·수출통제 강화는 공급망과 투자심리를 동시에 압박할 수 있습니다."
    return "거시 충격 이벤트가 시장 심리에 직접 영향을 줄 수 있습니다."


def _macro_news_rank_key(item: NewsItem) -> tuple[int, str]:
    text = item.title.lower()
    score = 0
    for rule in _RULES:
        if any(keyword in text for keyword in rule.any_keywords):
            score += _SEVERITY_SCORE.get(rule.severity, 1) * 10
        if rule.qualifier_keywords and any(keyword in text for keyword in rule.qualifier_keywords):
            score += 5
    source = (item.source or "").lower()
    if "reuters" in source:
        score += 5
    elif "associated press" in source or "ap" == source:
        score += 4
    elif "cnbc" in source or "yahoo" in source:
        score += 2
    return score, item.published_at


def _is_recent(item: NewsItem, run_date: date) -> bool:
    raw = str(item.published_at or "").strip()
    if not raw:
        return True
    normalized = raw.replace("Z", "+00:00")
    try:
        published = date.fromisoformat(normalized[:10])
    except ValueError:
        return True
    return (run_date - published).days <= 7


def _ddgs_verify_setting() -> str | bool:
    try:
        return certifi.where() if certifi is not None else True
    except Exception:
        return True
