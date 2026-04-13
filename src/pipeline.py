from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from pathlib import Path

from src.analyzer.research_note import analyze_tickers
from src.collector.macro import collect_macro_context
from src.collector.news_rss import collect_news_for_watchlist
from src.collector.price import collect_market_data, collect_market_overview
from src.output.alert import evaluate_alert_rules
from src.output.api_status import write_api_status_outputs
from src.output.markdown import write_outputs
from src.output.slack import send_daily_summary, send_pipeline_failure_alert, send_signal_alerts
from src.types import CollectedTickerData
from src.utils.config import load_portfolio, load_watchlist
from src.utils.datastore import get_datastore
from src.utils.env import is_env_flag_enabled, load_dotenv
from src.utils.portfolio import calculate_portfolio_summary
from src.utils.portfolio_risk import build_portfolio_risk_report
from src.utils.pipeline_logging import finalize_pipeline_logging, get_pipeline_logger, record_pipeline_event, start_pipeline_logging
from src.utils.signal_tracker import load_recent_signals, load_signal_stats, record_signals, update_signal_returns


def run_pipeline(run_date: date | None = None) -> None:
    load_dotenv()
    effective_date = run_date or date.today()
    start_pipeline_logging(effective_date)
    record_pipeline_event("pipeline", "info", "pipeline_started", run_date=effective_date.isoformat())

    success = False
    try:
        watchlist = load_watchlist()
        portfolio_holdings = load_portfolio()
        datastore = get_datastore(output_root=Path("output"))
        collected = collect_market_data(watchlist, effective_date)
        historical_price_rows = datastore.query_prices(tickers=[item.ticker for item in watchlist])
        collected = _merge_missing_prices_from_history(collected, historical_price_rows)
        market_overview = collect_market_overview()
        vix_data = _extract_vix_from_overview(market_overview)
        macro_context = collect_macro_context(effective_date, vix_data=vix_data)
        news_map = collect_news_for_watchlist(watchlist, effective_date)
        portfolio_summary = calculate_portfolio_summary(portfolio_holdings, collected)
        portfolio_account_size = portfolio_summary.total_market_value if portfolio_summary else None
        signal_csv_path = Path("output") / "data" / "signal_tracker.csv"
        signal_history_map = {
            item.ticker: load_recent_signals(signal_csv_path, item.ticker)
            for item in watchlist
        }
        if is_env_flag_enabled("ENABLE_CONVICTION_ROUTING", default=False):
            high_conviction = [
                item for item in watchlist
                if _score_conviction(collected[item.ticker], news_map.get(item.ticker, [])) >= 2
            ]
            normal_items = [item for item in watchlist if item not in high_conviction]
            analyses = analyze_tickers(
                normal_items,
                collected,
                news_map,
                effective_date,
                macro_context=macro_context,
                signal_history_map=signal_history_map,
                model_profile_name="standard",
                portfolio_account_size=portfolio_account_size,
            )
            if high_conviction:
                analyses.extend(
                    analyze_tickers(
                        high_conviction,
                        collected,
                        news_map,
                        effective_date,
                        macro_context=macro_context,
                        signal_history_map=signal_history_map,
                        model_profile_name="deep",
                        portfolio_account_size=portfolio_account_size,
                    )
                )
        else:
            analyses = analyze_tickers(
                watchlist,
                collected,
                news_map,
                effective_date,
                macro_context=macro_context,
                signal_history_map=signal_history_map,
                portfolio_account_size=portfolio_account_size,
            )
        portfolio_risk = build_portfolio_risk_report(portfolio_summary, collected)
        price_lookup = {ticker: data.price for ticker, data in collected.items() if data.price is not None}
        updated_signals = update_signal_returns(
            signal_csv_path,
            effective_date,
            price_lookup,
            price_history_rows=historical_price_rows,
        )
        record_signals(analyses, effective_date, price_lookup, signal_csv_path)
        datastore.sync_signal_history(signal_csv_path)
        signal_stats = load_signal_stats(signal_csv_path)
        direct_period_changes = {
            ticker: {"7d": data.price_change_7d, "30d": data.price_change_30d}
            for ticker, data in collected.items()
        }
        output_paths = write_outputs(
            analyses,
            effective_date,
            market_overview=market_overview,
            direct_period_changes=direct_period_changes,
            portfolio_summary=portfolio_summary,
            signal_stats=signal_stats,
            macro_context=macro_context,
            portfolio_risk=portfolio_risk,
        )
        send_daily_summary(
            analyses,
            effective_date,
            market_overview=market_overview,
            daily_note_path=output_paths.get("daily_path"),
            weekly_note_path=output_paths.get("weekly_path"),
            portfolio_summary=portfolio_summary,
            macro_context=macro_context,
        )
        signal_alerts = evaluate_alert_rules(watchlist, collected)
        send_signal_alerts(signal_alerts)
        success = True
        record_pipeline_event("pipeline", "info", "pipeline_completed", ticker_count=len(analyses), updated_signal_rows=updated_signals)
        write_api_status_outputs(effective_date, watchlist, output_root=Path("output"))
        datastore.record_analysis_run(run_date=effective_date, success=True, logger=get_pipeline_logger())
    except Exception as exc:
        send_pipeline_failure_alert(effective_date, str(exc))
        record_pipeline_event(
            "pipeline",
            "error",
            "pipeline_failed",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        get_datastore(output_root=Path("output")).record_analysis_run(
            run_date=effective_date,
            success=False,
            logger=get_pipeline_logger(),
        )
        raise
    finally:
        finalize_pipeline_logging(success)


def _extract_vix_from_overview(market_overview: list[dict[str, str]]) -> dict[str, str] | None:
    for entry in market_overview:
        if entry.get("label") == "VIX" or entry.get("symbol") == "^VIX":
            return {
                "price": entry.get("price", "N/A"),
                "change_percent": entry.get("change_percent", "N/A"),
            }
    return None


def _score_conviction(data: object, news_items: list[object] | None = None) -> int:
    from src.types import CollectedTickerData

    if not isinstance(data, CollectedTickerData):
        return 0

    score = 0
    flow = data.options_flow or {}
    if flow.get("flow_sentiment") == "bullish" and flow.get("unusual_activity"):
        score += 1
    if any(transaction.get("type") == "buy" for transaction in (data.insider_transactions or [])):
        score += 1
    if (data.analyst_estimate_revisions or {}).get("direction") == "up":
        score += 1
    if _headline_tone_score(news_items or []) > 0:
        score += 1
    if _is_atr_breakout(data):
        score += 1
    if _parse_numeric(data.relative_volume) is not None and _parse_numeric(data.relative_volume) >= 1.5:
        score += 1
    rsi_value = _parse_numeric((data.technical_indicators or {}).get("rsi_14", "N/A"))
    if rsi_value is not None and (rsi_value >= 70 or rsi_value <= 30):
        score += 1
    return score


def _parse_numeric(value: object) -> float | None:
    import re

    text = str(value or "").strip().replace(",", "")
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _is_atr_breakout(data: object) -> bool:
    from src.types import CollectedTickerData

    if not isinstance(data, CollectedTickerData):
        return False
    change_percent = data.change_percent
    atr_percent = _parse_numeric(data.atr_percent)
    if change_percent is None or atr_percent is None:
        return False
    return abs(change_percent) >= atr_percent


def _headline_tone_score(news_items: list[object]) -> int:
    positive_terms = ("beat", "surge", "raise", "upgrade", "growth", "record", "bull", "strong", "outperform")
    negative_terms = ("miss", "cut", "downgrade", "warning", "weak", "lawsuit", "bear", "decline", "fall")
    positive = 0
    negative = 0
    for item in news_items[:5]:
        title = str(getattr(item, "title", "") or "").lower()
        positive += sum(1 for term in positive_terms if term in title)
        negative += sum(1 for term in negative_terms if term in title)
    if positive > negative:
        return 1
    if negative > positive:
        return -1
    return 0


def _merge_missing_prices_from_history(
    collected: dict[str, CollectedTickerData],
    historical_price_rows: list[dict[str, str]],
) -> dict[str, CollectedTickerData]:
    latest_price_by_ticker: dict[str, float] = {}
    latest_date_by_ticker: dict[str, str] = {}
    for row in historical_price_rows:
        ticker = str(row.get("ticker", "")).strip().upper()
        row_date = str(row.get("date", "")).strip()
        price_value = _parse_price_value(row.get("price", ""))
        if not ticker or price_value is None or not row_date:
            continue
        previous_date = latest_date_by_ticker.get(ticker, "")
        if previous_date and previous_date >= row_date:
            continue
        latest_date_by_ticker[ticker] = row_date
        latest_price_by_ticker[ticker] = price_value

    patched = dict(collected)
    for ticker, payload in patched.items():
        price = getattr(payload, "price", None)
        if price is not None:
            continue
        fallback_price = latest_price_by_ticker.get(ticker)
        if fallback_price is None:
            continue
        patched[ticker] = replace(payload, price=fallback_price)
    return patched


def _parse_price_value(raw_value: object) -> float | None:
    text = str(raw_value or "").strip().replace(",", "")
    if not text or text == "N/A":
        return None
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None
