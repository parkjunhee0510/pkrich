from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from src.decision.decision_layer import print_factor_distribution
from src.types import CollectedTickerData, MarketRegime, NewsItem, TickerAnalysis

OUTPUT_ROOT = Path("output") / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump conviction factor distribution for latest ticker snapshots.")
    parser.add_argument("--tickers", nargs="*", help="Optional ticker filter")
    args = parser.parse_args()

    index_payload = _load_json(OUTPUT_ROOT / "index.json")
    latest_tickers = [str(item).upper() for item in (args.tickers or [])]
    analyses, collected = _load_latest_snapshots(latest_tickers)
    if not analyses:
        raise SystemExit("No ticker snapshots available for decision distribution dump.")

    regime = _build_market_regime(index_payload)
    signal_stats = index_payload.get("signal_stats", {}) if isinstance(index_payload, dict) else {}
    portfolio_risk = index_payload.get("portfolio_risk", {}) if isinstance(index_payload, dict) else {}
    signal_context = {
        **signal_stats,
        "_portfolio_risk": portfolio_risk,
    }
    print_factor_distribution(analyses, collected, regime, signal_context)


def _load_latest_snapshots(ticker_filter: list[str]) -> tuple[list[TickerAnalysis], dict[str, CollectedTickerData]]:
    analyses: list[TickerAnalysis] = []
    collected: dict[str, CollectedTickerData] = {}
    tickers_dir = OUTPUT_ROOT / "tickers"
    if not tickers_dir.exists():
        return analyses, collected

    for latest_path in sorted(tickers_dir.glob("*/latest.json")):
        payload = _load_json(latest_path).get("payload", {})
        ticker = str(payload.get("ticker", "")).upper()
        if not ticker:
            continue
        if ticker_filter and ticker not in ticker_filter:
            continue
        analysis = _build_analysis(payload)
        analyses.append(analysis)
        collected[ticker] = _build_collected_snapshot(payload)
    return analyses, collected


def _build_analysis(payload: dict) -> TickerAnalysis:
    news_references = [
        NewsItem(
            title=str(item.get("title", "")),
            source=str(item.get("source", "")),
            published_at=str(item.get("published_at", "")),
            link=str(item.get("link", "")),
            form_type=str(item.get("form_type", "")),
            item_number=str(item.get("item_number", "")),
            catalyst_type=str(item.get("catalyst_type", "")),
            importance_score=int(item.get("importance_score", 0) or 0),
        )
        for item in payload.get("news_references", [])
        if isinstance(item, dict)
    ]
    return TickerAnalysis(
        ticker=str(payload.get("ticker", "")),
        name=str(payload.get("name", "")),
        date=str(payload.get("date", "")),
        summary=str(payload.get("summary", "")),
        key_news=[str(item) for item in payload.get("key_news", [])],
        news_references=news_references,
        financial_highlights=[str(item) for item in payload.get("financial_highlights", [])],
        risks_or_watchpoints=[str(item) for item in payload.get("risks_or_watchpoints", [])],
        signal_or_takeaway=str(payload.get("signal_or_takeaway", "")),
        data_snapshot=_string_dict(payload.get("data_snapshot", {})),
        fundamentals=_string_dict(payload.get("fundamentals", {})),
        price_action=_string_dict(payload.get("price_action", {})),
        quarterly_financials=_list_of_string_dicts(payload.get("quarterly_financials", [])),
        upcoming_events=_list_of_string_dicts(payload.get("upcoming_events", [])),
        news_tone=dict(payload.get("news_tone", {}) or {}),
        trade_frame=_string_dict(payload.get("trade_frame", {})),
        options_summary=_string_dict(payload.get("options_summary", {})),
        signal_history=_list_of_string_dicts(payload.get("signal_history", [])),
        sector_comparison=dict(payload.get("sector_comparison", {}) or {}),
        peer_rank=dict(payload.get("peer_rank", {}) or {}),
        valuation_score=dict(payload.get("valuation_score", {}) or {}),
        analysis_consensus=dict(payload.get("analysis_consensus", {}) or {}),
        historical_prices=[],
    )


def _build_collected_snapshot(payload: dict) -> CollectedTickerData:
    snapshot = _string_dict(payload.get("data_snapshot", {}))
    fundamentals = _string_dict(payload.get("fundamentals", {}))
    price_action = _string_dict(payload.get("price_action", {}))
    options_summary = _string_dict(payload.get("options_summary", {}))
    earnings_setup = _string_dict(payload.get("earnings_setup", {}))
    price_value, currency = _parse_price_currency(snapshot.get("Price", ""))

    return CollectedTickerData(
        ticker=str(payload.get("ticker", "")),
        name=str(payload.get("name", "")),
        sector=str(snapshot.get("Sector", "")),
        price=price_value,
        change_percent=_parse_float(snapshot.get("Daily Change", "")),
        currency=currency,
        market_cap=str(snapshot.get("Market Cap", fundamentals.get("market_cap", "N/A"))),
        pe_ratio=str(snapshot.get("Trailing P/E", fundamentals.get("trailing_pe", "N/A"))),
        summary_note=str(payload.get("summary", "")),
        eps=str(snapshot.get("EPS", fundamentals.get("eps", "N/A"))),
        week52_high=str(snapshot.get("52W High", fundamentals.get("52w_high", "N/A"))),
        week52_low=str(snapshot.get("52W Low", fundamentals.get("52w_low", "N/A"))),
        sma_50=str(snapshot.get("50D SMA", "N/A")),
        sma_200=str(snapshot.get("200D SMA", "N/A")),
        volume=str(snapshot.get("Volume", fundamentals.get("volume", "N/A"))),
        avg_volume_3m=str(snapshot.get("3M Avg Volume", fundamentals.get("avg_volume_3m", "N/A"))),
        price_to_book=str(snapshot.get("Price/Book", fundamentals.get("price_to_book", "N/A"))),
        dividend_yield=str(snapshot.get("Dividend Yield", fundamentals.get("dividend_yield", "N/A"))),
        forward_eps=str(fundamentals.get("forward_eps", earnings_setup.get("forward_eps", "N/A"))),
        earnings_growth=str(fundamentals.get("earnings_growth", earnings_setup.get("earnings_growth", "N/A"))),
        short_float_pct=str(fundamentals.get("short_float_pct", "N/A")),
        short_ratio=str(fundamentals.get("short_ratio", "N/A")),
        analyst_target_price=str(fundamentals.get("analyst_target_price", "N/A")),
        analyst_recommendation=str(fundamentals.get("analyst_recommendation", "N/A")),
        analyst_count=str(fundamentals.get("analyst_count", "N/A")),
        held_by_insiders=str(fundamentals.get("held_by_insiders", "N/A")),
        held_by_institutions=str(fundamentals.get("held_by_institutions", "N/A")),
        implied_volatility=str(fundamentals.get("implied_volatility", "N/A")),
        quarterly_financials=_list_of_string_dicts(payload.get("quarterly_financials", [])),
        upcoming_events=_list_of_string_dicts(payload.get("upcoming_events", [])),
        price_change_7d=str(payload.get("period_changes", {}).get("7d", "N/A")),
        price_change_30d=str(payload.get("period_changes", {}).get("30d", "N/A")),
        atr_14d=str(price_action.get("atr_14d", "N/A")),
        atr_percent=str(price_action.get("atr_percent", "N/A")),
        relative_volume=str(price_action.get("relative_volume", "N/A")),
        gap_percent=str(price_action.get("gap_percent", "N/A")),
        price_vs_sma50=str(price_action.get("price_vs_sma50", "N/A")),
        price_vs_sma200=str(price_action.get("price_vs_sma200", "N/A")),
        week52_position=str(price_action.get("week52_position", "N/A")),
        rs_vs_spy=str(price_action.get("rs_vs_spy", "N/A")),
        rs_vs_sector_etf=str(price_action.get("rs_vs_sector_etf", "N/A")),
        options_summary=options_summary,
        open_price=str(snapshot.get("Open", "N/A")),
        high_price=str(snapshot.get("High", "N/A")),
        low_price=str(snapshot.get("Low", "N/A")),
        close_price=str(snapshot.get("Close", "N/A")),
        day_volume=str(snapshot.get("Volume", "N/A")),
    )


def _build_market_regime(index_payload: dict) -> MarketRegime:
    regime_payload = index_payload.get("market_regime", {}) if isinstance(index_payload, dict) else {}
    return MarketRegime(
        regime=str(regime_payload.get("regime", "neutral")),
        confidence=int(regime_payload.get("confidence", 0) or 0),
        drivers=dict(regime_payload.get("drivers", {}) or {}),
        implication=str(regime_payload.get("implication", "")),
        assessed_at=str(regime_payload.get("assessed_at", "")),
    )


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _string_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _list_of_string_dicts(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            rows.append({str(key): str(entry) for key, entry in item.items()})
    return rows


def _parse_price_currency(raw_value: str) -> tuple[float | None, str]:
    parts = str(raw_value).split()
    currency = parts[-1] if len(parts) >= 2 and parts[-1].isalpha() else "USD"
    numeric = _parse_float(parts[0] if parts else "")
    return numeric, currency


def _parse_float(raw_value: str) -> float | None:
    text = str(raw_value or "").replace(",", "").strip()
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


if __name__ == "__main__":
    main()
