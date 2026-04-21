from __future__ import annotations

from datetime import date, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse

from src.collector.ir_rss import collect_ir_rss_news
from src.collector.news_search import search_news
from src.collector.news_title_utils import looks_like_unresolved_placeholder
from src.collector.sec_edgar import collect_sec_edgar_news
from src.types import NewsItem, WatchlistItem
from src.utils.config import load_simple_mapping
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event
from src.utils.sec_filings import extract_sec_filing_tag, is_sec_filing_reference

_GOOGLE_NEWS_PROVIDERS = [
    {"name": "Google News", "site_filter": ""},
    {"name": "Yahoo Finance", "site_filter": "finance.yahoo.com"},
    {"name": "Reuters", "site_filter": "reuters.com"},
    {"name": "Associated Press", "site_filter": "apnews.com"},
    {"name": "CNBC", "site_filter": "cnbc.com"},
    {"name": "MarketWatch", "site_filter": "marketwatch.com"},
]
_NEWS_FOCUS_TERMS = ["earnings", "guidance", "analyst", "upgrade", "downgrade", "outlook", "forecast", "results"]
_DEFAULT_SOURCE_PRIORITIES = {
    "reuters": 5,
    "associated press": 4,
    "the associated press": 4,
    "ap": 4,
    "ap news": 4,
    "sec edgar": 4,
    "bloomberg": 3,
    "cnbc": 2,
    "ir rss": 2,
    "apple newsroom": 2,
    "microsoft source": 2,
    "nvidia newsroom": 2,
    "yahoo finance": 2,
    "marketwatch": 1,
    "seeking alpha": 1,
    "duckduckgo": 0,
    "rss": 0,
    "fallback": -1,
}
_MAX_NEWS_AGE_DAYS = 180
_DEFAULT_MAX_ITEMS_PER_SOURCE = 2
_DEFAULT_SEC_FILING_TAG_PRIORITIES = {
    "실적": 140,
    "배당": 110,
    "주주총회": 90,
    "기타 공시": 60,
}
_THESIS_RECAP_TERMS = ["why ", "how ", "what is", "explained", "recap", "analysis of"]


def collect_news_for_watchlist(
    watchlist: list[WatchlistItem],
    run_date: date,
) -> dict[str, list[NewsItem]]:
    external_enabled = is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True)
    google_available = can_open_tcp_connection("news.google.com", 443)
    duckduckgo_available = can_open_tcp_connection("duckduckgo.com", 443)
    sec_available = can_open_tcp_connection("data.sec.gov", 443)

    news_map: dict[str, list[NewsItem]] = {}
    for item in watchlist:
        if not external_enabled:
            news_map[item.ticker] = _fallback_news(
                item,
                run_date,
                "외부 수집이 비활성화되어 뉴스 요청을 건너뛰었습니다.",
            )
            record_pipeline_event(
                "collector",
                "info",
                "news_collection_skipped",
                ticker=item.ticker,
                reason="external_fetch_disabled",
            )
            continue

        rss_news = _collect_rss_news(item, google_available)
        sec_news = collect_sec_edgar_news(item, run_date, network_available=sec_available)
        ir_news = collect_ir_rss_news(item)
        search_results = search_news(item) if duckduckgo_available else []
        merged = _merge_news_items(
            item,
            rss_news + sec_news + ir_news,
            search_results,
            max_items=5,
            run_date=run_date,
        )
        if merged:
            news_map[item.ticker] = merged
            record_pipeline_event(
                "collector",
                "info",
                "news_collection_completed",
                ticker=item.ticker,
                rss_result_count=len(rss_news),
                sec_result_count=len(sec_news),
                ir_result_count=len(ir_news),
                supplemental_result_count=len(search_results),
                merged_result_count=len(merged),
                top_scored_headline_title=merged[0].title,
            )
            continue

        if not google_available and not duckduckgo_available and not sec_available:
            news_map[item.ticker] = _fallback_news(
                item,
                run_date,
                "네트워크를 사용할 수 없어 뉴스 요청을 건너뛰었습니다.",
            )
            record_pipeline_event(
                "collector",
                "warning",
                "news_source_unavailable",
                ticker=item.ticker,
                source="MultiSource",
                error_type="ConnectionUnavailable",
                error_message="Google News, SEC EDGAR, and DuckDuckGo were unavailable.",
            )
            continue

        news_map[item.ticker] = _fallback_news(
            item,
            run_date,
            f"{run_date.isoformat()} 기준 {item.ticker} 관련 최근 뉴스를 가져오지 못했습니다.",
        )
        record_pipeline_event(
            "collector",
            "warning",
            "news_fallback_applied",
            ticker=item.ticker,
            error_type="NoNewsResults",
            error_message="No qualifying news items remained after filtering and ranking.",
        )
    return news_map


def _collect_rss_news(item: WatchlistItem, google_available: bool) -> list[NewsItem]:
    if not google_available:
        return []

    entries: list[NewsItem] = []
    for provider in _GOOGLE_NEWS_PROVIDERS:
        entries.extend(_collect_google_news_provider(item, provider))
    return entries


def _collect_google_news_provider(item: WatchlistItem, provider: dict[str, str]) -> list[NewsItem]:
    try:
        import feedparser  # type: ignore
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "news_provider_failed",
            ticker=item.ticker,
            source=provider["name"],
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return []

    try:
        query = _build_google_news_query(item, provider["site_filter"])
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={quote_plus(query)}")
        entries: list[NewsItem] = []
        for entry in feed.entries[:5]:
            title = str(getattr(entry, "title", "")).strip()
            if not title:
                continue
            if looks_like_unresolved_placeholder(title):
                record_pipeline_event(
                    "collector",
                    "info",
                    "news_title_placeholder_dropped",
                    ticker=item.ticker,
                    source=provider["name"],
                    title=title[:80],
                )
                continue
            source_title = provider["name"]
            if hasattr(entry, "source"):
                source_title = str(getattr(entry, "source", {}).get("title", provider["name"])) or provider["name"]
            entries.append(
                NewsItem(
                    title=title,
                    source=source_title,
                    published_at=str(getattr(entry, "published", "")),
                    link=str(getattr(entry, "link", "")),
                )
            )
        return _filter_excluded_news(entries, item.exclude_keywords)
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "news_provider_failed",
            ticker=item.ticker,
            source=provider["name"],
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return []


def _fallback_news(item: WatchlistItem, run_date: date, title: str) -> list[NewsItem]:
    return [
        NewsItem(
            title=title,
            source="fallback",
            published_at=run_date.isoformat(),
            link="",
        )
    ]


def _merge_news_items(
    item: WatchlistItem,
    primary: list[NewsItem],
    supplemental: list[NewsItem],
    max_items: int,
    run_date: date | None = None,
) -> list[NewsItem]:
    filtered_items = _filter_excluded_news(primary + supplemental, item.exclude_keywords)

    merged: list[NewsItem] = []
    seen_titles: set[str] = set()
    seen_hosted_titles: set[tuple[str, str]] = set()

    for candidate in filtered_items:
        if not _is_displayable_news_item(candidate):
            continue
        normalized_title = _normalize_title(candidate.title)
        hostname = _normalize_hostname(candidate.link)
        hosted_key = (hostname, normalized_title)
        if not normalized_title or normalized_title in seen_titles:
            continue
        if hostname and hosted_key in seen_hosted_titles:
            continue
        seen_titles.add(normalized_title)
        if hostname:
            seen_hosted_titles.add(hosted_key)
        merged.append(candidate)

    ranked_candidates = _filter_stale_news_candidates(merged, run_date)
    ranked = sorted(
        ranked_candidates,
        key=lambda news_item: _news_rank_key(item, news_item, run_date),
        reverse=True,
    )
    diversified = _apply_source_diversity_cap(ranked, max_items=max_items)
    return diversified[:max_items]


def _build_google_news_query(item: WatchlistItem, site_filter: str) -> str:
    company_name = " ".join(item.name.replace("Corporation", "").replace("Corp.", "").replace("Inc.", "").split())
    focus_terms = " ".join(_NEWS_FOCUS_TERMS[:4])
    query_parts = [item.ticker, company_name, "stock", *item.keywords[:2], focus_terms]
    if site_filter:
        query_parts.append(f"site:{site_filter}")
    return " ".join(part for part in query_parts if part).strip()


def _filter_excluded_news(items: list[NewsItem], exclude_keywords: list[str]) -> list[NewsItem]:
    if not exclude_keywords:
        return items

    normalized_excludes = [_normalize_title(keyword) for keyword in exclude_keywords if _normalize_title(keyword)]
    if not normalized_excludes:
        return items

    filtered: list[NewsItem] = []
    for item in items:
        normalized_title = _normalize_title(item.title)
        if any(exclude in normalized_title for exclude in normalized_excludes):
            continue
        filtered.append(item)
    return filtered


def _is_displayable_news_item(item: NewsItem) -> bool:
    title = str(item.title or "").strip()
    link = str(item.link or "").strip()
    return bool(title or link)


def _news_rank_key(item: WatchlistItem, news_item: NewsItem, run_date: date | None) -> tuple[int, datetime, int, str]:
    published_dt = _parse_published_at(news_item.published_at)
    source_priority = load_source_priorities().get((news_item.source or "").strip().lower(), 0)
    title = _normalize_title(news_item.title)
    company_name = _normalize_title(item.name.replace("Corporation", "").replace("Corp.", "").replace("Inc.", ""))
    catalyst_type = _resolve_catalyst_type(news_item)

    score = source_priority * 100
    if published_dt != datetime.min:
        anchor_date = run_date or date.today()
        days_old = max((anchor_date - published_dt.date()).days, 0)
        score += _age_score_by_catalyst(catalyst_type, days_old)
    if item.ticker.lower() in title:
        score += 20
    if company_name and any(token in title for token in company_name.split() if len(token) >= 3):
        score += 12
    for keyword in item.keywords[:2]:
        normalized_keyword = _normalize_title(keyword)
        if normalized_keyword and normalized_keyword in title:
            score += 8
    for term in _NEWS_FOCUS_TERMS:
        if term in title:
            score += 5
    if is_sec_filing_reference(news_item):
        score += news_item.importance_score or _load_sec_filing_tag_priorities(item).get(extract_sec_filing_tag(news_item.title), 0)
    if any(term in title for term in _THESIS_RECAP_TERMS):
        score -= 30
    if not news_item.link:
        score -= 15
    if (news_item.source or "").strip().lower() == "fallback":
        score -= 100

    return (score, published_dt, source_priority, title)


def load_source_priorities() -> dict[str, int]:
    try:
        raw_config = load_simple_mapping("config/output.yaml")
        configured = raw_config.get("news_source_priority", {})
        if not isinstance(configured, dict):
            return _DEFAULT_SOURCE_PRIORITIES
        return {str(key).strip().lower(): int(value) for key, value in configured.items()}
    except Exception:
        return _DEFAULT_SOURCE_PRIORITIES


def _load_max_items_per_source() -> int:
    try:
        raw_config = load_simple_mapping("config/output.yaml")
        configured = raw_config.get("news_source_max_items_per_source")
        if isinstance(configured, (int, float)) and int(configured) > 0:
            return int(configured)
    except Exception:
        return _DEFAULT_MAX_ITEMS_PER_SOURCE
    return _DEFAULT_MAX_ITEMS_PER_SOURCE


def _load_sec_filing_tag_priorities(item: WatchlistItem) -> dict[str, int]:
    try:
        raw_config = load_simple_mapping("config/output.yaml")
        configured = raw_config.get("sec_filing_tag_priority", {})
        priorities = dict(_DEFAULT_SEC_FILING_TAG_PRIORITIES)
        if isinstance(configured, dict):
            for key, value in configured.items():
                tag = str(key).strip()
                if not tag:
                    continue
                priorities[tag] = int(value)
        for tag, value in item.sec_filing_tag_priority.items():
            normalized_tag = str(tag).strip()
            if not normalized_tag:
                continue
            priorities[normalized_tag] = int(value)
        return priorities
    except Exception:
        merged = dict(_DEFAULT_SEC_FILING_TAG_PRIORITIES)
        merged.update(item.sec_filing_tag_priority)
        return merged


def _normalize_title(title: str) -> str:
    return " ".join(title.strip().lower().split())


def _normalize_hostname(link: str) -> str:
    if not link:
        return ""
    try:
        return (urlparse(link).hostname or "").strip().lower()
    except ValueError:
        return ""


def _normalize_source_name(source: str) -> str:
    return " ".join((source or "").strip().lower().split())


def _parse_published_at(raw_value: str) -> datetime:
    if not raw_value:
        return datetime.min
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(raw_value).replace(tzinfo=None)
    except (TypeError, ValueError):
        return datetime.min


def _filter_stale_news_candidates(
    items: list[NewsItem],
    run_date: date | None,
) -> list[NewsItem]:
    if run_date is None:
        return items

    recent_items = [item for item in items if _is_recent_news_item(item, run_date)]
    if recent_items:
        return recent_items

    return items


def _apply_source_diversity_cap(items: list[NewsItem], *, max_items: int) -> list[NewsItem]:
    cap = _load_max_items_per_source()
    selected: list[NewsItem] = []
    overflow: list[NewsItem] = []
    counts_by_source: dict[str, int] = {}

    for item in items:
        normalized_source = _normalize_source_name(item.source)
        current_count = counts_by_source.get(normalized_source, 0)
        if current_count < cap:
            selected.append(item)
            counts_by_source[normalized_source] = current_count + 1
        else:
            overflow.append(item)

    minimum_target = min(max_items, 3)
    if len(selected) < minimum_target:
        for item in overflow:
            selected.append(item)
            if len(selected) >= minimum_target:
                break

    return selected


def _is_recent_news_item(item: NewsItem, run_date: date) -> bool:
    published_at = _parse_published_at(item.published_at)
    if published_at == datetime.min:
        return True
    days_old = (run_date - published_at.date()).days
    if days_old < 0:
        return True
    return days_old <= _MAX_NEWS_AGE_DAYS


def _resolve_catalyst_type(item: NewsItem) -> str:
    if item.catalyst_type:
        return item.catalyst_type

    normalized_source = _normalize_source_name(item.source)
    if normalized_source in {"sec edgar", "ir rss", "apple newsroom", "microsoft source", "nvidia newsroom"}:
        return "hard"
    if normalized_source in {"reuters", "associated press", "ap news", "cnbc", "marketwatch", "yahoo finance"}:
        return "medium"
    return "soft"


def _age_score_by_catalyst(catalyst_type: str, days_old: int) -> int:
    if catalyst_type == "hard":
        return max(0, 30 - days_old)
    if catalyst_type == "medium":
        return max(0, 14 - days_old)
    return max(0, 7 - days_old)
