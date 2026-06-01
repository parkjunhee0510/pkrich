"""Provider-independent search evidence collection and cache loading."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from src.collector.rate_limiter import RateLimiterHub
from src.collector.search_evidence_config import SearchEvidenceConfig, load_search_evidence_config
from src.collector.search_evidence_priority import build_priority_refresh_plan
from src.output.schema import SCHEMA_VERSION
from src.utils.budget_guard import estimate_profile_call_cost, evaluate_budget_guard
from src.utils.model_config import load_budget_guard_config, load_model_profile
from src.utils.pipeline_logging import record_pipeline_event


@dataclass(frozen=True)
class SearchEvidenceItem:
    ticker: str
    query: str
    title: str
    url: str
    published_at: str = ""
    snippet: str = ""
    evidence_type: str = "news"
    relevance_score: float = 0.0
    freshness_hours: int | None = None

    def to_dict(self) -> dict[str, Any]:
        query = str(self.query or "").strip()
        return {
            "ticker": _normalize_ticker(self.ticker),
            "query": query,
            "source_domain": source_domain(self.url),
            "title": str(self.title or "").strip(),
            "url": str(self.url or "").strip(),
            "published_at": str(self.published_at or "").strip(),
            "snippet": str(self.snippet or "").strip(),
            "evidence_type": str(self.evidence_type or "news").strip() or "news",
            "relevance_score": _clamp_float(self.relevance_score),
            "freshness_hours": self.freshness_hours,
            "query_hash": query_hash(query),
        }


@dataclass(frozen=True)
class _CacheLookup:
    path: Path
    source_date: date
    age_hours: int


class SearchEvidenceProvider(Protocol):
    def search(self, *, ticker: str, queries: list[str], run_date: date) -> list[SearchEvidenceItem]:
        ...


def collect_search_evidence(
    *,
    run_date: date,
    tickers: list[str],
    priority_tickers: list[str] | None = None,
    priority_context_by_ticker: dict[str, dict[str, Any]] | None = None,
    cache_root: Path = Path("output") / "cache" / "search_evidence",
    config: SearchEvidenceConfig | None = None,
    provider: SearchEvidenceProvider | None = None,
    run_cost_so_far_usd: float = 0.0,
) -> dict[str, Any]:
    """Load structured search evidence and optionally refresh it via provider."""
    config = config or load_search_evidence_config()
    normalized_tickers = [_normalize_ticker(ticker) for ticker in tickers if _normalize_ticker(ticker)]
    normalized_priority_tickers = _ordered_subset(
        [_normalize_ticker(ticker) for ticker in (priority_tickers or []) if _normalize_ticker(ticker)],
        normalized_tickers,
    )
    items: list[SearchEvidenceItem] = []
    cache_hit_count = 0
    cache_error_count = 0
    stale_cache_hit_count = 0
    provider_call_count = 0
    provider_error_count = 0
    cache_dir = cache_root / run_date.isoformat()
    cached_tickers: set[str] = set()
    cache_error_tickers: set[str] = set()
    cache_source_dates: dict[str, str] = {}
    cache_age_hours_by_ticker: dict[str, int] = {}
    provider_candidate_tickers: set[str] = set()
    provider_attempted_tickers: set[str] = set()
    provider_error_tickers: set[str] = set()
    provider_unavailable_tickers: set[str] = set()
    provider_budget_blocked_tickers: set[str] = set()
    provider_rate_limited_tickers: set[str] = set()

    for ticker in normalized_tickers:
        cache_lookup = _find_cache_path(cache_root, run_date, ticker, config.cache_ttl_hours)
        if cache_lookup is None:
            continue
        cache_path = cache_lookup.path
        try:
            cached_items = _load_cached_items(cache_path, fallback_ticker=ticker)
        except Exception as exc:
            cache_error_count += 1
            cache_error_tickers.add(ticker)
            record_pipeline_event(
                "collector",
                "warning",
                "search_evidence_cache_invalid",
                ticker=ticker,
                path=str(cache_path),
                error_type=type(exc).__name__,
                error_message=str(exc)[:200],
            )
            continue
        if cached_items:
            cache_hit_count += 1
            if cache_lookup.age_hours > 0:
                stale_cache_hit_count += 1
            cached_tickers.add(ticker)
            cache_source_dates[ticker] = cache_lookup.source_date.isoformat()
            cache_age_hours_by_ticker[ticker] = cache_lookup.age_hours
            items.extend(cached_items)

    stale_cache_tickers = {
        ticker for ticker, age_hours in cache_age_hours_by_ticker.items() if age_hours > 0
    }
    priority_plan = build_priority_refresh_plan(
        tickers=normalized_tickers,
        router_priority_tickers=normalized_priority_tickers,
        mode=config.mode,
        cached_tickers=cached_tickers,
        stale_cache_tickers=stale_cache_tickers,
        priority_context_by_ticker=priority_context_by_ticker or {},
    )
    normalized_priority_tickers = priority_plan.priority_tickers
    priority_refresh_reasons = priority_plan.reasons_by_ticker

    if config.mode == "openai":
        search_provider = provider or _build_openai_provider(config)
        tickers_for_provider = [
            ticker
            for ticker in _provider_refresh_order(normalized_tickers, normalized_priority_tickers)
            if ticker not in cached_tickers
        ][: config.max_search_tickers_per_run]
        provider_candidate_tickers.update(tickers_for_provider)

        if search_provider is None:
            if tickers_for_provider:
                provider_unavailable_tickers.update(tickers_for_provider)
                record_pipeline_event(
                    "collector",
                    "warning",
                    "search_evidence_provider_unavailable",
                    provider=config.provider,
                    skipped_ticker_count=len(tickers_for_provider),
                    reason="missing_openai_client_or_api_key",
                )
        elif _budget_guard_allows_search(config, tickers_for_provider, run_cost_so_far_usd):
            limiter = _search_rate_limiter(config)
            for ticker in tickers_for_provider:
                queries = build_search_queries(ticker, config)
                estimated_tokens = _estimated_search_tokens(config, len(queries))
                if not limiter.acquire_llm(
                    "openai_search_evidence",
                    estimated_tokens=estimated_tokens,
                    timeout=config.rate_limit_timeout_seconds,
                ):
                    provider_rate_limited_tickers.add(ticker)
                    record_pipeline_event(
                        "collector",
                        "warning",
                        "search_evidence_rate_limited",
                        ticker=ticker,
                        estimated_tokens=estimated_tokens,
                    )
                    continue
                try:
                    provider_attempted_tickers.add(ticker)
                    provider_items = search_provider.search(
                        ticker=ticker,
                        queries=queries,
                        run_date=run_date,
                    )
                except Exception as exc:
                    provider_error_count += 1
                    provider_error_tickers.add(ticker)
                    record_pipeline_event(
                        "collector",
                        "warning",
                        "search_evidence_provider_failed",
                        ticker=ticker,
                        provider=config.provider,
                        error_type=type(exc).__name__,
                        error_message=str(exc)[:200],
                    )
                    continue

                provider_call_count += 1
                if provider_items:
                    items.extend(provider_items)
                    _write_cached_items(cache_dir / f"{ticker}.json", provider_items)
        else:
            provider_budget_blocked_tickers.update(tickers_for_provider)

    return build_search_evidence_payload(
        run_date=run_date,
        tickers=normalized_tickers,
        items=items,
        cache_hit_count=cache_hit_count,
        cache_error_count=cache_error_count,
        stale_cache_hit_count=stale_cache_hit_count,
        cache_ttl_hours=config.cache_ttl_hours,
        provider_name="openai" if provider_call_count else "cache",
        provider_call_count=provider_call_count,
        provider_error_count=provider_error_count,
        mode=config.mode,
        priority_tickers=normalized_priority_tickers,
        priority_refresh_reasons=priority_refresh_reasons,
        cache_source_dates=cache_source_dates,
        cache_age_hours_by_ticker=cache_age_hours_by_ticker,
        cache_error_tickers=cache_error_tickers,
        provider_candidate_tickers=provider_candidate_tickers,
        provider_attempted_tickers=provider_attempted_tickers,
        provider_error_tickers=provider_error_tickers,
        provider_unavailable_tickers=provider_unavailable_tickers,
        provider_budget_blocked_tickers=provider_budget_blocked_tickers,
        provider_rate_limited_tickers=provider_rate_limited_tickers,
    )


def build_search_evidence_payload(
    *,
    run_date: date,
    tickers: list[str],
    items: list[SearchEvidenceItem],
    cache_hit_count: int,
    cache_error_count: int,
    stale_cache_hit_count: int = 0,
    cache_ttl_hours: int = 0,
    provider_name: str = "cache",
    provider_call_count: int = 0,
    provider_error_count: int = 0,
    mode: str = "cache",
    priority_tickers: list[str] | set[str] | tuple[str, ...] = (),
    priority_refresh_reasons: dict[str, list[str]] | None = None,
    cache_source_dates: dict[str, str] | None = None,
    cache_age_hours_by_ticker: dict[str, int] | None = None,
    cache_error_tickers: set[str] | None = None,
    provider_candidate_tickers: set[str] | None = None,
    provider_attempted_tickers: set[str] | None = None,
    provider_error_tickers: set[str] | None = None,
    provider_unavailable_tickers: set[str] | None = None,
    provider_budget_blocked_tickers: set[str] | None = None,
    provider_rate_limited_tickers: set[str] | None = None,
) -> dict[str, Any]:
    normalized_tickers = [_normalize_ticker(ticker) for ticker in tickers if _normalize_ticker(ticker)]
    normalized_priority_tickers = _normalize_priority_tickers(priority_tickers, normalized_tickers)
    priority_set = set(normalized_priority_tickers)
    priority_refresh_reasons_by_ticker = _normalize_priority_refresh_reasons(
        priority_refresh_reasons or {},
        normalized_tickers,
        priority_set,
    )
    cache_source_dates = {
        _normalize_ticker(ticker): str(source_date or "")
        for ticker, source_date in (cache_source_dates or {}).items()
        if _normalize_ticker(ticker)
    }
    cache_age_hours_by_ticker = {
        _normalize_ticker(ticker): _non_negative_int(age_hours)
        for ticker, age_hours in (cache_age_hours_by_ticker or {}).items()
        if _normalize_ticker(ticker)
    }
    cache_error_tickers = cache_error_tickers or set()
    provider_candidate_tickers = provider_candidate_tickers or set()
    provider_attempted_tickers = provider_attempted_tickers or set()
    provider_error_tickers = provider_error_tickers or set()
    provider_unavailable_tickers = provider_unavailable_tickers or set()
    provider_budget_blocked_tickers = provider_budget_blocked_tickers or set()
    provider_rate_limited_tickers = provider_rate_limited_tickers or set()
    item_dicts = [item.to_dict() for item in items]
    by_ticker = {
        ticker: _summarize_ticker(
            ticker,
            item_dicts,
            mode=mode,
            priority_for_refresh=ticker in priority_set,
            cache_source_date=cache_source_dates.get(ticker, ""),
            cache_age_hours=cache_age_hours_by_ticker.get(ticker, 0),
            cache_error=ticker in cache_error_tickers,
            provider_candidate=ticker in provider_candidate_tickers,
            provider_attempted=ticker in provider_attempted_tickers,
            provider_error=ticker in provider_error_tickers,
            provider_unavailable=ticker in provider_unavailable_tickers,
            provider_budget_blocked=ticker in provider_budget_blocked_tickers,
            provider_rate_limited=ticker in provider_rate_limited_tickers,
            priority_refresh_reasons=priority_refresh_reasons_by_ticker.get(ticker, []),
        )
        for ticker in normalized_tickers
    }
    searched_ticker_count = sum(1 for summary in by_ticker.values() if summary["evidence_count"] > 0)
    status_counts: dict[str, int] = {}
    for summary in by_ticker.values():
        status = str(summary.get("evidence_status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
    priority_status_counts: dict[str, int] = {}
    for ticker in normalized_priority_tickers:
        if ticker not in by_ticker:
            continue
        status = str(by_ticker[ticker].get("evidence_status", "unknown"))
        priority_status_counts[status] = priority_status_counts.get(status, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "date": run_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": str(provider_name or "cache"),
        "items": item_dicts,
        "by_ticker": by_ticker,
        "run_summary": {
            "candidate_ticker_count": len(normalized_tickers),
            "searched_ticker_count": searched_ticker_count,
            "cache_hit_count": int(cache_hit_count),
            "cache_error_count": int(cache_error_count),
            "stale_cache_hit_count": int(stale_cache_hit_count),
            "cache_ttl_hours": int(cache_ttl_hours),
            "provider_call_count": int(provider_call_count),
            "provider_error_count": int(provider_error_count),
            "priority_tickers": normalized_priority_tickers,
            "priority_ticker_count": len(normalized_priority_tickers),
            "priority_refresh_reasons": _count_priority_refresh_reasons(
                normalized_priority_tickers,
                priority_refresh_reasons_by_ticker,
            ),
            "priority_status_counts": priority_status_counts,
            "priority_refresh_candidate_count": len(priority_set & set(provider_candidate_tickers)),
            "provider_candidate_count": len(provider_candidate_tickers),
            "skipped_ticker_count": max(0, len(normalized_tickers) - searched_ticker_count),
            "status_counts": status_counts,
        },
    }


def build_search_queries(ticker: str, config: SearchEvidenceConfig) -> list[str]:
    normalized_ticker = _normalize_ticker(ticker)
    queries: list[str] = []
    for template in config.query_templates:
        query = str(template or "").replace("{ticker}", normalized_ticker).strip()
        if query and query not in queries:
            queries.append(query)
        if len(queries) >= config.max_queries_per_ticker:
            break
    return queries or [f"{normalized_ticker} latest company evidence"]


def query_hash(query: str) -> str:
    digest = hashlib.sha256(str(query or "").strip().encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def source_domain(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    return parsed.netloc.lower()


def _load_cached_items(path: Path, *, fallback_ticker: str) -> list[SearchEvidenceItem]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_items = payload.get("items", [])
    if not isinstance(raw_items, list):
        return []
    items: list[SearchEvidenceItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        items.append(
            SearchEvidenceItem(
                ticker=str(raw.get("ticker") or fallback_ticker),
                query=str(raw.get("query") or ""),
                title=str(raw.get("title") or ""),
                url=str(raw.get("url") or ""),
                published_at=str(raw.get("published_at") or ""),
                snippet=str(raw.get("snippet") or ""),
                evidence_type=str(raw.get("evidence_type") or "news"),
                relevance_score=_clamp_float(raw.get("relevance_score", 0.0)),
                freshness_hours=_optional_int(raw.get("freshness_hours")),
            )
        )
    return items


def _find_cache_path(cache_root: Path, run_date: date, ticker: str, cache_ttl_hours: int) -> _CacheLookup | None:
    normalized_ticker = _normalize_ticker(ticker)
    if not normalized_ticker:
        return None
    ttl_hours = _non_negative_int(cache_ttl_hours)
    max_days_back = ttl_hours // 24
    for days_back in range(max_days_back + 1):
        age_hours = days_back * 24
        if age_hours > ttl_hours:
            continue
        source_date = run_date - timedelta(days=days_back)
        cache_path = cache_root / source_date.isoformat() / f"{normalized_ticker}.json"
        if cache_path.exists():
            return _CacheLookup(path=cache_path, source_date=source_date, age_hours=age_hours)
    return None


def _write_cached_items(path: Path, items: list[SearchEvidenceItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"items": [item.to_dict() for item in items]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_openai_provider(config: SearchEvidenceConfig) -> SearchEvidenceProvider | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        from src.collector.providers.search.openai_web_search import OpenAIWebSearchProvider

        profile = load_model_profile(profile_name=config.model_profile)
        return OpenAIWebSearchProvider(model=profile.model, tool_type=config.tool_type)
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "search_evidence_provider_unavailable",
            provider=config.provider,
            error_type=type(exc).__name__,
            error_message=str(exc)[:200],
        )
        return None


def _budget_guard_allows_search(
    config: SearchEvidenceConfig,
    tickers_for_provider: list[str],
    run_cost_so_far_usd: float,
) -> bool:
    if not tickers_for_provider:
        return True
    profile = load_model_profile(profile_name=config.model_profile)
    query_count = len(tickers_for_provider) * max(1, config.max_queries_per_ticker)
    estimated_cost = estimate_profile_call_cost(
        input_tokens=query_count * config.estimated_input_tokens_per_query,
        output_tokens=query_count * config.estimated_output_tokens_per_query,
        input_cost_per_1m=profile.input_cost_per_1m_tokens,
        output_cost_per_1m=profile.output_cost_per_1m_tokens,
    )
    budget_config = load_budget_guard_config()
    budget_decision = evaluate_budget_guard(
        config=budget_config,
        path="search_evidence",
        profile=config.model_profile,
        estimated_incremental_cost_usd=estimated_cost,
        run_cost_so_far_usd=run_cost_so_far_usd,
    )
    record_pipeline_event("collector", "info", "budget_guard_decision", **budget_decision.to_log_fields())
    return budget_decision.allowed


def _search_rate_limiter(config: SearchEvidenceConfig) -> RateLimiterHub:
    hub = RateLimiterHub()
    hub.register_llm(
        "openai_search_evidence",
        requests_per_minute=config.requests_per_minute,
        tokens_per_minute=config.tokens_per_minute,
    )
    return hub


def _estimated_search_tokens(config: SearchEvidenceConfig, query_count: int) -> int:
    return max(
        1,
        int(query_count)
        * (config.estimated_input_tokens_per_query + config.estimated_output_tokens_per_query),
    )


def _summarize_ticker(
    ticker: str,
    items: list[dict[str, Any]],
    *,
    mode: str = "cache",
    priority_for_refresh: bool = False,
    cache_source_date: str = "",
    cache_age_hours: int = 0,
    cache_error: bool = False,
    provider_candidate: bool = False,
    provider_attempted: bool = False,
    provider_error: bool = False,
    provider_unavailable: bool = False,
    provider_budget_blocked: bool = False,
    provider_rate_limited: bool = False,
    priority_refresh_reasons: list[str] | None = None,
) -> dict[str, Any]:
    ticker_items = [item for item in items if item.get("ticker") == ticker]
    domains = sorted({str(item.get("source_domain") or "") for item in ticker_items if item.get("source_domain")})
    evidence_count = len(ticker_items)
    freshness_values = [
        int(item["freshness_hours"])
        for item in ticker_items
        if isinstance(item.get("freshness_hours"), int)
    ]
    avg_relevance = (
        sum(float(item.get("relevance_score") or 0.0) for item in ticker_items) / evidence_count
        if evidence_count
        else 0.0
    )
    coverage_score = min(1.0, (evidence_count / 5.0) * 0.7 + min(len(domains), 3) / 3.0 * 0.3)
    freshness_score = _freshness_score(min(freshness_values) if freshness_values else None)
    evidence_status, provider_status = _evidence_status(
        evidence_count=evidence_count,
        mode=mode,
        cache_error=cache_error,
        provider_candidate=provider_candidate,
        provider_attempted=provider_attempted,
        provider_error=provider_error,
        provider_unavailable=provider_unavailable,
        provider_budget_blocked=provider_budget_blocked,
        provider_rate_limited=provider_rate_limited,
    )
    return {
        "coverage_score": round(coverage_score, 4),
        "source_diversity": len(domains),
        "freshness_score": freshness_score,
        "evidence_count": evidence_count,
        "average_relevance_score": round(avg_relevance, 4),
        "top_domains": domains[:5],
        "evidence_status": evidence_status,
        "provider_status": provider_status,
        "priority_for_refresh": priority_for_refresh,
        "priority_refresh_reasons": list(priority_refresh_reasons or []),
        "cache_source_date": cache_source_date,
        "cache_age_hours": _non_negative_int(cache_age_hours),
    }


def _evidence_status(
    *,
    evidence_count: int,
    mode: str,
    cache_error: bool,
    provider_candidate: bool,
    provider_attempted: bool,
    provider_error: bool,
    provider_unavailable: bool,
    provider_budget_blocked: bool,
    provider_rate_limited: bool,
) -> tuple[str, str]:
    if evidence_count > 0:
        return "covered", "searched" if provider_attempted else "cache_hit"
    if cache_error:
        return "cache_error", "cache_error"
    if provider_error:
        return "provider_error", "provider_error"
    if provider_unavailable:
        return "provider_unavailable", "provider_unavailable"
    if provider_rate_limited:
        return "not_refreshed", "rate_limited"
    if provider_budget_blocked:
        return "not_refreshed", "budget_blocked"
    if provider_attempted:
        return "no_evidence", "searched_no_results"
    if str(mode).lower() == "openai" and not provider_candidate:
        return "not_refreshed", "not_selected"
    return "no_evidence", "not_requested"


def _provider_refresh_order(
    normalized_tickers: list[str],
    normalized_priority_tickers: list[str],
) -> list[str]:
    priority = _ordered_subset(normalized_priority_tickers, normalized_tickers)
    return priority + [ticker for ticker in normalized_tickers if ticker not in set(priority)]


def _ordered_subset(values: list[str], allowed_values: list[str]) -> list[str]:
    allowed = set(allowed_values)
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in allowed and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _normalize_priority_tickers(
    priority_tickers: list[str] | set[str] | tuple[str, ...],
    normalized_tickers: list[str],
) -> list[str]:
    if isinstance(priority_tickers, set):
        raw_priority_tickers = sorted(_normalize_ticker(ticker) for ticker in priority_tickers)
    else:
        raw_priority_tickers = [_normalize_ticker(ticker) for ticker in priority_tickers]
    return _ordered_subset([ticker for ticker in raw_priority_tickers if ticker], normalized_tickers)


def _normalize_priority_refresh_reasons(
    priority_refresh_reasons: dict[str, list[str]],
    normalized_tickers: list[str],
    priority_set: set[str],
) -> dict[str, list[str]]:
    allowed = set(normalized_tickers) & priority_set
    result: dict[str, list[str]] = {}
    for raw_ticker, raw_reasons in priority_refresh_reasons.items():
        ticker = _normalize_ticker(raw_ticker)
        if ticker not in allowed or not isinstance(raw_reasons, list):
            continue
        reasons: list[str] = []
        seen: set[str] = set()
        for raw_reason in raw_reasons:
            reason = str(raw_reason or "").strip()
            if reason and reason not in seen:
                reasons.append(reason)
                seen.add(reason)
        result[ticker] = reasons
    for ticker in priority_set:
        result.setdefault(ticker, ["router_selected"])
    return result


def _count_priority_refresh_reasons(
    normalized_priority_tickers: list[str],
    reasons_by_ticker: dict[str, list[str]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ticker in normalized_priority_tickers:
        for reason in reasons_by_ticker.get(ticker, []):
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _freshness_score(freshness_hours: int | None) -> float:
    if freshness_hours is None:
        return 0.0
    if freshness_hours <= 24:
        return 1.0
    if freshness_hours <= 72:
        return 0.8
    if freshness_hours <= 168:
        return 0.5
    return 0.2


def _normalize_ticker(ticker: str) -> str:
    return str(ticker or "").strip().upper()


def _clamp_float(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, parsed))


def _optional_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _non_negative_int(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)
