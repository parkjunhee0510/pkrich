"""Provider-independent search evidence collection and cache loading."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from src.collector.rate_limiter import RateLimiterHub
from src.collector.search_evidence_config import SearchEvidenceConfig, load_search_evidence_config
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


class SearchEvidenceProvider(Protocol):
    def search(self, *, ticker: str, queries: list[str], run_date: date) -> list[SearchEvidenceItem]:
        ...


def collect_search_evidence(
    *,
    run_date: date,
    tickers: list[str],
    cache_root: Path = Path("output") / "cache" / "search_evidence",
    config: SearchEvidenceConfig | None = None,
    provider: SearchEvidenceProvider | None = None,
    run_cost_so_far_usd: float = 0.0,
) -> dict[str, Any]:
    """Load structured search evidence and optionally refresh it via provider."""
    config = config or load_search_evidence_config()
    normalized_tickers = [_normalize_ticker(ticker) for ticker in tickers if _normalize_ticker(ticker)]
    items: list[SearchEvidenceItem] = []
    cache_hit_count = 0
    cache_error_count = 0
    provider_call_count = 0
    provider_error_count = 0
    cache_dir = cache_root / run_date.isoformat()
    cached_tickers: set[str] = set()

    for ticker in normalized_tickers:
        cache_path = cache_dir / f"{ticker}.json"
        if not cache_path.exists():
            continue
        try:
            cached_items = _load_cached_items(cache_path, fallback_ticker=ticker)
        except Exception as exc:
            cache_error_count += 1
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
            cached_tickers.add(ticker)
            items.extend(cached_items)

    if config.mode == "openai":
        search_provider = provider or _build_openai_provider(config)
        tickers_for_provider = [
            ticker
            for ticker in normalized_tickers
            if ticker not in cached_tickers
        ][: config.max_search_tickers_per_run]

        if search_provider is None:
            if tickers_for_provider:
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
                    record_pipeline_event(
                        "collector",
                        "warning",
                        "search_evidence_rate_limited",
                        ticker=ticker,
                        estimated_tokens=estimated_tokens,
                    )
                    continue
                try:
                    provider_items = search_provider.search(
                        ticker=ticker,
                        queries=queries,
                        run_date=run_date,
                    )
                except Exception as exc:
                    provider_error_count += 1
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

    return build_search_evidence_payload(
        run_date=run_date,
        tickers=normalized_tickers,
        items=items,
        cache_hit_count=cache_hit_count,
        cache_error_count=cache_error_count,
        provider_name="openai" if provider_call_count else "cache",
        provider_call_count=provider_call_count,
        provider_error_count=provider_error_count,
    )


def build_search_evidence_payload(
    *,
    run_date: date,
    tickers: list[str],
    items: list[SearchEvidenceItem],
    cache_hit_count: int,
    cache_error_count: int,
    provider_name: str = "cache",
    provider_call_count: int = 0,
    provider_error_count: int = 0,
) -> dict[str, Any]:
    normalized_tickers = [_normalize_ticker(ticker) for ticker in tickers if _normalize_ticker(ticker)]
    item_dicts = [item.to_dict() for item in items]
    by_ticker = {
        ticker: _summarize_ticker(ticker, item_dicts)
        for ticker in normalized_tickers
    }
    searched_ticker_count = sum(1 for summary in by_ticker.values() if summary["evidence_count"] > 0)

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
            "provider_call_count": int(provider_call_count),
            "provider_error_count": int(provider_error_count),
            "skipped_ticker_count": max(0, len(normalized_tickers) - searched_ticker_count),
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


def _summarize_ticker(ticker: str, items: list[dict[str, Any]]) -> dict[str, Any]:
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
    return {
        "coverage_score": round(coverage_score, 4),
        "source_diversity": len(domains),
        "freshness_score": freshness_score,
        "evidence_count": evidence_count,
        "average_relevance_score": round(avg_relevance, 4),
        "top_domains": domains[:5],
    }


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
