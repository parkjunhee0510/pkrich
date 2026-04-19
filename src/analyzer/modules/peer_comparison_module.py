from __future__ import annotations

from typing import Any

from src.analyzer import research_note
from src.analyzer.base import AnalysisContext, AnalysisModule, ModuleResult
from src.analyzer.peer_rank import build_peer_rank
from src.analyzer.peer_selector import PeerSelector
from src.utils.quarterly_financials import extract_latest_revenue_growth


class PeerComparisonModule(AnalysisModule):
    name = "peer_comparison_module"
    requires = {"fundamentals", "historical_prices", "price", "peer_candidates"}
    produces = {"sector_comparison", "peer_selection", "peer_rank"}
    priority = 5
    llm_required = False

    def __init__(self) -> None:
        self.selector = PeerSelector()

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        grouped = self._build_watchlist_fallback_candidates(ctx)
        results: dict[str, dict[str, Any]] = {}
        selected_diagnostics: dict[str, dict[str, Any]] = {}

        for item in ctx.watchlist:
            ticker = item.ticker
            market = ctx.collected[ticker]
            raw_payload = ctx.raw_payload_by_ticker.get(ticker, {})
            existing_peer_rank = dict(ctx.intermediate_results.get(ticker, {}).get("peer_rank", {}) or {})
            candidates = list(raw_payload.get("peer_candidates", []))
            candidate_by_ticker = {
                str(candidate.get("ticker", "")).strip().upper(): candidate
                for candidate in candidates
                if isinstance(candidate, dict)
            }
            source = "finnhub"
            selected = self.selector.select_peers(
                ticker,
                item.sector or market.sector or "N/A",
                market.market_cap,
                candidates,
            )
            if not selected:
                source = "watchlist_fallback"
                selected = self.selector.select_peers(
                    ticker,
                    item.sector or market.sector or "N/A",
                    market.market_cap,
                    grouped.get(ticker, []),
                )

            raw_context = self._build_raw_context(item.ticker, market, selected)
            peer_rank = build_peer_rank(
                company_metrics={
                    "pe_ratio": market.pe_ratio,
                    "price_change_30d": market.price_change_30d,
                    "roe": market.fundamental_metrics.get("roe", "N/A") if isinstance(market.fundamental_metrics, dict) else "N/A",
                    "revenue_growth": extract_latest_revenue_growth(market.quarterly_financials),
                    "dividend_yield": market.dividend_yield,
                },
                peer_metrics=[
                    {
                        "pe_ratio": peer.pe_ratio,
                        "price_change_30d": peer.price_change_30d,
                        "roe": peer.roe,
                        "revenue_growth": peer.revenue_growth or str(
                            candidate_by_ticker.get(peer.ticker, {}).get(
                                "revenue_growth",
                                candidate_by_ticker.get(peer.ticker, {}).get("earnings_growth", "N/A"),
                            )
                        ),
                        "dividend_yield": peer.dividend_yield or str(candidate_by_ticker.get(peer.ticker, {}).get("dividend_yield", "N/A")),
                    }
                    for peer in selected
                ],
            )
            if not peer_rank:
                peer_rank = existing_peer_rank
            results[ticker] = {
                "sector_comparison": research_note._format_sector_comparison(raw_context),
                "peer_selection": {
                    "selected_peers": self.selector.serialize(selected),
                    "source": source,
                },
                "peer_rank": peer_rank,
            }
            selected_diagnostics[ticker] = {
                "selected_peers": self.selector.serialize(selected),
                "source": source,
                "sector": str(item.sector or market.sector or "N/A"),
                "market_cap": market.market_cap,
            }

        return ModuleResult(
            results_by_ticker=results,
            diagnostics={"selected_peers_by_ticker": selected_diagnostics},
        )

    def _build_watchlist_fallback_candidates(self, ctx: AnalysisContext) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in ctx.watchlist:
            market = ctx.collected[item.ticker]
            sector_key = (item.sector or market.sector or "N/A").strip() or "N/A"
            grouped.setdefault(sector_key, []).append(
                {
                    "ticker": item.ticker,
                    "sector": sector_key,
                    "market_cap": market.market_cap,
                    "avg_volume": market.avg_volume_3m,
                    "pe_ratio": market.pe_ratio,
                    "roe": market.fundamental_metrics.get("roe", "N/A") if isinstance(market.fundamental_metrics, dict) else "N/A",
                    "gross_margin": market.fundamental_metrics.get("gross_margin", "N/A") if isinstance(market.fundamental_metrics, dict) else "N/A",
                    "price_change_30d": market.price_change_30d,
                    "rs_vs_spy": market.rs_vs_spy,
                    "revenue_growth": extract_latest_revenue_growth(market.quarterly_financials),
                    "dividend_yield": market.dividend_yield,
                }
            )

        candidates_by_ticker: dict[str, list[dict[str, Any]]] = {}
        for item in ctx.watchlist:
            market = ctx.collected[item.ticker]
            sector_key = (item.sector or market.sector or "N/A").strip() or "N/A"
            candidates_by_ticker[item.ticker] = [
                entry for entry in grouped.get(sector_key, []) if entry.get("ticker") != item.ticker
            ]
        return candidates_by_ticker

    def _build_raw_context(self, ticker: str, market: Any, selected: list[Any]) -> dict[str, str]:
        if not selected:
            return {}

        average_pe = self._average_numeric([peer.pe_ratio for peer in selected], suffix='x')
        average_roe = self._average_numeric([peer.roe for peer in selected], suffix='%')
        average_margin = self._average_numeric([peer.gross_margin for peer in selected], suffix='%')
        average_30d = self._average_numeric([peer.price_change_30d for peer in selected], suffix='%')
        average_rs = self._average_numeric([peer.rs_vs_spy for peer in selected], suffix='%')
        return {
            "sector": str(market.sector or "N/A"),
            "peer_names": "/".join(peer.ticker for peer in selected[:5]),
            "peer_count": str(len(selected)),
            "peer_avg_roe": average_roe,
            "peer_avg_gross_margin": average_margin,
            "ticker_roe": market.fundamental_metrics.get("roe", "N/A") if isinstance(market.fundamental_metrics, dict) else "N/A",
            "ticker_gross_margin": market.fundamental_metrics.get("gross_margin", "N/A") if isinstance(market.fundamental_metrics, dict) else "N/A",
            "average_pe": average_pe,
            "average_price_change_30d": average_30d,
            "average_rs_vs_spy": average_rs,
            "ticker_pe": market.pe_ratio,
            "ticker_price_change_30d": market.price_change_30d,
            "ticker_rs_vs_spy": market.rs_vs_spy,
            "enhanced": "true",
        }

    def _average_numeric(self, values: list[str], *, suffix: str) -> str:
        usable: list[float] = []
        for value in values:
            parsed = self._parse_numeric(value)
            if parsed is not None:
                usable.append(parsed)
        if not usable:
            return "N/A"
        return f"{sum(usable) / len(usable):.2f}{suffix}"

    def _parse_numeric(self, value: Any) -> float | None:
        text = str(value or "").strip()
        if not text or text == "N/A":
            return None
        cleaned = (
            text.replace(",", "")
            .replace("%", "")
            .replace("x", "")
            .replace("X", "")
            .split()[0]
        )
        try:
            return float(cleaned)
        except ValueError:
            return None
