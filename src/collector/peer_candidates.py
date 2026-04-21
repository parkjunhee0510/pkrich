from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from src.collector.finnhub import collect_finnhub_peers, is_finnhub_ready
from src.collector.fmp import collect_fmp_peer_metrics, is_fmp_ready
from src.collector.yfinance_peer_metrics import (
    collect_yfinance_peer_metrics,
    is_yfinance_peer_ready,
)
from src.types import CollectedTickerData, WatchlistItem
from src.utils.datastore import Datastore, get_datastore
from src.utils.pipeline_logging import record_pipeline_event


def month_key_for_date(run_date: date) -> str:
    return f"{run_date.year:04d}-{run_date.month:02d}"


def load_peer_candidates(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    run_date: date,
    *,
    output_root: Path | None = None,
    datastore: Datastore | None = None,
) -> dict[str, list[dict[str, Any]]]:
    peer_store = datastore or get_datastore(output_root=output_root or Path("output"), backend="sqlite")
    month_key = month_key_for_date(run_date)
    results: dict[str, list[dict[str, Any]]] = {}
    unresolved: list[WatchlistItem] = []

    for item in watchlist:
        cached = peer_store.get_peer_selection_cache(item.ticker, month_key)
        if isinstance(cached, dict):
            selected = cached.get("selected_peers")
            if isinstance(selected, list) and selected:
                results[item.ticker] = [dict(entry) for entry in selected if isinstance(entry, dict)]
                record_pipeline_event(
                    "collector",
                    "info",
                    "peer_selection_cache_hit",
                    ticker=item.ticker,
                    month_key=month_key,
                    peer_count=len(results[item.ticker]),
                )
                continue
        unresolved.append(item)

    if not unresolved or not is_finnhub_ready():
        return results

    peer_symbols_by_ticker: dict[str, list[str]] = {}
    all_peer_symbols: list[str] = []
    for item in unresolved:
        peers = collect_finnhub_peers(item.ticker)
        if not peers:
            continue
        peer_symbols_by_ticker[item.ticker] = peers
        for peer in peers:
            if peer not in all_peer_symbols:
                all_peer_symbols.append(peer)

    yf_metrics = collect_yfinance_peer_metrics(all_peer_symbols) if is_yfinance_peer_ready() else {}
    fmp_metrics = collect_fmp_peer_metrics(all_peer_symbols) if is_fmp_ready() else {}
    peer_metrics = _merge_peer_metrics(yf_metrics, fmp_metrics)

    for item in unresolved:
        sector = (item.sector or collected[item.ticker].sector or "N/A").strip() or "N/A"
        ticker_candidates: list[dict[str, Any]] = []
        for peer in peer_symbols_by_ticker.get(item.ticker, []):
            metrics = dict(peer_metrics.get(peer, {}))
            metrics["ticker"] = peer
            metrics.setdefault("sector", sector)
            ticker_candidates.append(metrics)
        if ticker_candidates:
            results[item.ticker] = ticker_candidates

    return results


def _merge_peer_metrics(
    primary: dict[str, dict[str, Any]],
    secondary: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Merge two provider metric maps. ``primary`` wins; ``secondary`` fills blanks."""
    merged: dict[str, dict[str, Any]] = {}
    tickers = set(primary.keys()) | set(secondary.keys())
    for ticker in tickers:
        combined: dict[str, Any] = {}
        for source in (secondary, primary):  # primary last so it overrides
            for key, value in source.get(ticker, {}).items():
                text = str(value or "").strip()
                if not text or text.upper() == "N/A":
                    continue
                combined[key] = value
        if combined:
            merged[ticker] = combined
    return merged


_PEER_METRIC_FIELDS = (
    "pe_ratio",
    "roe",
    "gross_margin",
    "price_change_30d",
    "rs_vs_spy",
    "revenue_growth",
    "dividend_yield",
    "market_cap",
)


def _peer_payload_has_usable_metrics(payload: dict[str, Any]) -> bool:
    """Return True if at least one selected peer has ≥1 non-N/A metric.

    Guards against caching throttled/empty FMP responses for the entire month.
    """
    selected = payload.get("selected_peers") if isinstance(payload, dict) else None
    if not isinstance(selected, list):
        return False
    for peer in selected:
        if not isinstance(peer, dict):
            continue
        for field_name in _PEER_METRIC_FIELDS:
            value = str(peer.get(field_name, "") or "").strip()
            if value and value.upper() != "N/A":
                return True
    return False


def persist_peer_selections(
    diagnostics: dict[str, Any],
    run_date: date,
    *,
    output_root: Path | None = None,
    datastore: Datastore | None = None,
) -> None:
    module_diagnostics = diagnostics.get("module_diagnostics", {}) if isinstance(diagnostics, dict) else {}
    peer_diag = module_diagnostics.get("peer_comparison_module", {}) if isinstance(module_diagnostics, dict) else {}
    selected_by_ticker = peer_diag.get("selected_peers_by_ticker", {}) if isinstance(peer_diag, dict) else {}
    if not isinstance(selected_by_ticker, dict) or not selected_by_ticker:
        return

    peer_store = datastore or get_datastore(output_root=output_root or Path("output"), backend="sqlite")
    month_key = month_key_for_date(run_date)
    for ticker, payload in selected_by_ticker.items():
        if not isinstance(payload, dict):
            continue
        if not _peer_payload_has_usable_metrics(payload):
            record_pipeline_event(
                "collector",
                "warning",
                "peer_selection_cache_skipped_empty",
                ticker=str(ticker),
                month_key=month_key,
                reason="all_peer_metrics_na",
            )
            continue
        peer_store.set_peer_selection_cache(str(ticker), month_key, payload)
