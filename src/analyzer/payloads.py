from __future__ import annotations

from datetime import date
from typing import Any

from src.analyzer import research_note
from src.analyzer.peer_rank import build_peer_rank
from src.types import CollectedTickerData, NewsItem, TickerAnalysis, WatchlistItem
from src.utils.quarterly_financials import extract_latest_revenue_growth


def build_raw_payloads(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    *,
    signal_history_map: dict[str, list[dict[str, str]]] | None = None,
    peer_candidates_by_ticker: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, dict[str, Any]]:
    deduped_news_map = {item.ticker: research_note._dedupe_news_items(news_map.get(item.ticker, [])) for item in watchlist}
    watchlist_peer_metrics = _build_watchlist_peer_metrics(watchlist, collected)
    payloads: dict[str, dict[str, Any]] = {}
    for item in watchlist:
        market = collected[item.ticker]
        peer_candidates = list((peer_candidates_by_ticker or {}).get(item.ticker, []))
        peer_rank = _build_payload_peer_rank(
            item=item,
            market=market,
            peer_candidates=peer_candidates,
            watchlist_peer_metrics=watchlist_peer_metrics,
        )
        payloads[item.ticker] = {
            'ticker': item.ticker,
            'name': item.name,
            'sector': item.sector,
            'price': market.price,
            'change_percent': market.change_percent,
            'currency': market.currency,
            'market_cap': market.market_cap,
            'pe_ratio': market.pe_ratio,
            'eps': market.eps,
            'forward_eps': market.forward_eps,
            'earnings_growth': market.earnings_growth,
            'price_to_book': market.price_to_book,
            'dividend_yield': market.dividend_yield,
            'volume': market.volume,
            'sma_50': market.sma_50,
            'sma_200': market.sma_200,
            'week52_high': market.week52_high,
            'week52_low': market.week52_low,
            'price_action': {
                'price_change_30d': market.price_change_30d,
                'atr_14d': market.atr_14d,
                'atr_percent': market.atr_percent,
                'relative_volume': market.relative_volume,
                'gap_percent': market.gap_percent,
                'price_vs_sma50': market.price_vs_sma50,
                'price_vs_sma200': market.price_vs_sma200,
                'week52_position': market.week52_position,
                'rs_vs_spy': market.rs_vs_spy,
                'rs_vs_sector_etf': market.rs_vs_sector_etf,
            },
            'positioning': {
                'short_float_pct': market.short_float_pct,
                'short_ratio': market.short_ratio,
                'analyst_target_price': market.analyst_target_price,
                'analyst_recommendation': market.analyst_recommendation,
                'analyst_count': market.analyst_count,
                'held_by_insiders': market.held_by_insiders,
                'held_by_institutions': market.held_by_institutions,
                'implied_volatility': market.implied_volatility,
            },
            'options_summary': market.options_summary,
            'analyst_estimate_revisions': market.analyst_estimate_revisions,
            'insider_transactions': market.insider_transactions[:6],
            'institutional_changes': market.institutional_changes,
            'fmp_earnings_surprises': market.fmp_earnings_surprises[:4],
            'options_flow': market.options_flow,
            'recommendation_trends': market.recommendation_trends[:3],
            'fundamental_metrics': market.fundamental_metrics,
            'technical_indicators': market.technical_indicators,
            'quarterly_financials': market.quarterly_financials[:4],
            'signal_history': (signal_history_map or {}).get(item.ticker, [])[:5],
            'sector_peer_context': {},
            'peer_candidates': peer_candidates,
            'peer_rank': peer_rank,
            'upcoming_events': market.upcoming_events[:3],
            'news': [
                {
                    'title': article.title,
                    'source': article.source,
                    'published_at': article.published_at,
                    'link': article.link,
                }
                for article in deduped_news_map.get(item.ticker, [])
            ],
        }
    return payloads


def build_fallback_payloads(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
    *,
    raw_payload_by_ticker: dict[str, dict[str, Any]] | None = None,
    signal_history_map: dict[str, list[dict[str, str]]] | None = None,
    account_size_hint: float | None = None,
) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    raw_payloads = raw_payload_by_ticker or build_raw_payloads(
        watchlist,
        collected,
        news_map,
        signal_history_map=signal_history_map,
    )
    for item in watchlist:
        peer_rank = dict(raw_payloads.get(item.ticker, {}).get("peer_rank", {}) or {})
        analysis = research_note._build_fallback_analysis(
            item,
            collected,
            news_map,
            run_date,
            signal_history=(signal_history_map or {}).get(item.ticker, []),
            sector_comparison=research_note._format_sector_comparison(
                raw_payloads.get(item.ticker, {}).get("sector_peer_context", {})
            ),
            peer_rank=peer_rank,
            account_size_hint=account_size_hint,
        )
        payloads[item.ticker] = research_note._analysis_to_payload(analysis)
    return payloads


def analyses_from_payloads(
    watchlist: list[WatchlistItem],
    payloads: dict[str, dict[str, Any]],
) -> list[TickerAnalysis]:
    return [
        research_note._analysis_from_payload(payloads[item.ticker])
        for item in watchlist
        if item.ticker in payloads
    ]


def payloads_from_analyses(
    analyses: list[TickerAnalysis],
) -> dict[str, dict[str, Any]]:
    return {
        analysis.ticker: research_note._analysis_to_payload(analysis)
        for analysis in analyses
    }


def _build_watchlist_peer_metrics(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for item in watchlist:
        market = collected[item.ticker]
        sector_key = (item.sector or market.sector or "N/A").strip() or "N/A"
        grouped.setdefault(sector_key, []).append(
            {
                "ticker": item.ticker,
                "pe_ratio": market.pe_ratio,
                "price_change_30d": market.price_change_30d,
                "roe": market.fundamental_metrics.get("roe", "N/A") if isinstance(market.fundamental_metrics, dict) else "N/A",
                "revenue_growth": extract_latest_revenue_growth(market.quarterly_financials),
                "dividend_yield": market.dividend_yield,
            }
        )
    return grouped


def _build_payload_peer_rank(
    *,
    item: WatchlistItem,
    market: CollectedTickerData,
    peer_candidates: list[dict[str, Any]],
    watchlist_peer_metrics: dict[str, list[dict[str, str]]],
) -> dict[str, object]:
    peer_metrics: list[dict[str, str]] = []
    used_candidate_metrics = False
    for peer in peer_candidates:
        if not isinstance(peer, dict):
            continue
        used_candidate_metrics = True
        peer_metrics.append(
            {
                "pe_ratio": str(peer.get("pe_ratio", "N/A")),
                "price_change_30d": str(peer.get("price_change_30d", "N/A")),
                "roe": str(peer.get("roe", "N/A")),
                "revenue_growth": str(peer.get("revenue_growth", peer.get("earnings_growth", "N/A"))),
                "dividend_yield": str(peer.get("dividend_yield", "N/A")),
            }
        )

    if len(peer_metrics) < 2:
        sector_key = (item.sector or market.sector or "N/A").strip() or "N/A"
        peer_metrics = [
            peer
            for peer in watchlist_peer_metrics.get(sector_key, [])
            if peer.get("ticker") != item.ticker
        ]
    payload = build_peer_rank(
        company_metrics={
            "pe_ratio": market.pe_ratio,
            "price_change_30d": market.price_change_30d,
            "roe": market.fundamental_metrics.get("roe", "N/A") if isinstance(market.fundamental_metrics, dict) else "N/A",
            "revenue_growth": extract_latest_revenue_growth(market.quarterly_financials),
            "dividend_yield": market.dividend_yield,
        },
        peer_metrics=peer_metrics,
    )
    if payload or not used_candidate_metrics:
        return payload

    sector_key = (item.sector or market.sector or "N/A").strip() or "N/A"
    fallback_peer_metrics = [
        peer
        for peer in watchlist_peer_metrics.get(sector_key, [])
        if peer.get("ticker") != item.ticker
    ]
    return build_peer_rank(
        company_metrics={
            "pe_ratio": market.pe_ratio,
            "price_change_30d": market.price_change_30d,
            "roe": market.fundamental_metrics.get("roe", "N/A") if isinstance(market.fundamental_metrics, dict) else "N/A",
            "revenue_growth": extract_latest_revenue_growth(market.quarterly_financials),
            "dividend_yield": market.dividend_yield,
        },
        peer_metrics=fallback_peer_metrics,
    )
