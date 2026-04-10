from __future__ import annotations

import csv
import io
import json
import math
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from time import sleep
from typing import Any
from urllib import error, parse, request

from src.types import CollectedTickerData, WatchlistItem
from src.collector.options import collect_options_summary
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

_ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
_ALPHA_VANTAGE_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
_ALPHA_VANTAGE_CSV_CACHE: dict[tuple[str, str, str], list[dict[str, str]]] = {}
_ALPHA_VANTAGE_LAST_CALL_AT = 0.0
_ALPHA_VANTAGE_DELAY_SECONDS = 12.0
_MARKET_INDICES = [
    ("^GSPC", "S&P 500", ["^spx", "^spx.us", "spx.us"]),
    ("^NDX", "NASDAQ 100", ["^ndx", "^ndx.us", "ndx.us"]),
    ("^VIX", "VIX", ["^vix", "^vix.us", "vix.us"]),
]
_SPY_BENCHMARK = ("SPY", ["spy.us"])
_EVENT_LOOKAHEAD_DAYS = 14
_EARNINGS_LOOKAHEAD_DAYS = 90


def collect_market_data(
    watchlist: list[WatchlistItem],
    run_date: date,
) -> dict[str, CollectedTickerData]:
    results: dict[str, CollectedTickerData] = {}
    benchmark_change_30d = _collect_benchmark_change_30d(run_date)
    for item in watchlist:
        results[item.ticker] = _collect_single_ticker(item, run_date, benchmark_change_30d=benchmark_change_30d)
        sleep(0.1)
    return results


def collect_market_overview() -> list[dict[str, str]]:
    if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
        return []

    results: list[dict[str, str]] = []
    yfinance_ready = can_open_tcp_connection("query1.finance.yahoo.com", 443)
    stooq_ready = can_open_tcp_connection("stooq.com", 443)

    yf_module: Any | None = None
    if yfinance_ready:
        try:
            import yfinance as yf  # type: ignore

            _configure_yfinance_cache(yf)
            yf_module = yf
        except Exception:
            yf_module = None

    for symbol, label, stooq_candidates in _MARKET_INDICES:
        price: float | None = None
        change_percent: float | None = None
        provider_used = ""

        if yf_module is not None:
            try:
                ticker = yf_module.Ticker(symbol)
                history = ticker.history(period="5d", interval="1d")
                info = getattr(ticker, "info", {}) or {}
                price, change_percent = _select_price_snapshot(history, info)
                if price is not None:
                    provider_used = "yfinance"
            except Exception as exc:
                record_pipeline_event(
                    "collector",
                    "warning",
                    "market_overview_provider_failed",
                    source="yfinance",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    label=label,
                )

        if price is None and stooq_ready:
            fallback_price, fallback_change = _fetch_stooq_price_snapshot(symbol, candidates=stooq_candidates)
            if fallback_price is not None:
                price = fallback_price
                change_percent = fallback_change
                provider_used = "stooq"

        if provider_used:
            record_pipeline_event("collector", "info", "data_provider_used", source=provider_used, label=label)

        results.append(
            {
                "label": label,
                "symbol": symbol,
                "price": f"{price:,.2f}" if price is not None else "N/A",
                "change": f"{change_percent:+.2f}%" if change_percent is not None else "N/A",
            }
        )
        sleep(0.1)

    return results


def _collect_single_ticker(
    item: WatchlistItem,
    run_date: date,
    *,
    benchmark_change_30d: float | None = None,
) -> CollectedTickerData:
    if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
        return _fallback_market_data(item, "외부 수집이 비활성화되어 Yahoo Finance 요청을 건너뛰었습니다.")

    providers_used: list[str] = []
    yfinance_ready = can_open_tcp_connection("query1.finance.yahoo.com", 443)
    stooq_ready = can_open_tcp_connection("stooq.com", 443)
    alpha_ready = bool(os.getenv("ALPHAVANTAGE_API_KEY")) and can_open_tcp_connection("www.alphavantage.co", 443)

    price: float | None = None
    change_percent: float | None = None
    currency = "USD"
    market_cap = "N/A"
    pe_ratio = "N/A"
    eps = "N/A"
    week52_high = "N/A"
    week52_low = "N/A"
    sma_50 = "N/A"
    sma_200 = "N/A"
    volume = "N/A"
    avg_volume_3m = "N/A"
    price_to_book = "N/A"
    dividend_yield = "N/A"
    forward_eps = "N/A"
    earnings_growth = "N/A"
    short_float_pct = "N/A"
    short_ratio = "N/A"
    analyst_target_price = "N/A"
    analyst_recommendation = "N/A"
    analyst_count = "N/A"
    held_by_insiders = "N/A"
    held_by_institutions = "N/A"
    implied_volatility = "N/A"
    quarterly_financials: list[dict[str, str]] = []
    upcoming_events: list[dict[str, str]] = []

    price_change_7d = "N/A"
    price_change_30d = "N/A"
    atr_14d = "N/A"
    atr_percent = "N/A"
    relative_volume = "N/A"
    gap_percent = "N/A"
    price_vs_sma50 = "N/A"
    price_vs_sma200 = "N/A"
    week52_position = "N/A"
    rs_vs_spy = "N/A"
    options_summary: dict[str, str] = {}

    if yfinance_ready:
        try:
            import yfinance as yf  # type: ignore

            _configure_yfinance_cache(yf)
            ticker = yf.Ticker(item.ticker)
            history = ticker.history(period="6mo", interval="1d")
            info = getattr(ticker, "info", {}) or {}
            price, change_percent = _select_price_snapshot(history, info)
            open_price = _coerce_finite_float(info.get("regularMarketOpen"))
            previous_close = _coerce_finite_float(info.get("previousClose"))
            currency = str(info.get("currency", "USD") or "USD")
            market_cap = _format_large_number(info.get("marketCap"))
            pe_ratio = _format_ratio(info.get("trailingPE"))
            eps = _format_ratio(info.get("trailingEps"))
            week52_high = _format_ratio(info.get("fiftyTwoWeekHigh"))
            week52_low = _format_ratio(info.get("fiftyTwoWeekLow"))
            sma_50 = _format_ratio(info.get("fiftyDayAverage"))
            sma_200 = _format_ratio(info.get("twoHundredDayAverage"))
            volume = _format_large_number(info.get("volume"))
            avg_volume_3m = _format_large_number(info.get("averageVolume"))
            price_to_book = _format_ratio(info.get("priceToBook"))
            dividend_yield = _format_percent_ratio(info.get("dividendYield"))
            forward_eps = _format_ratio(info.get("forwardEps") or info.get("epsForward"))
            if forward_eps == "N/A":
                forward_eps = _derive_forward_eps(price, info.get("forwardPE"))
            if forward_eps == "N/A":
                forward_eps = _extract_forward_eps_from_analyst_targets(getattr(ticker, "analyst_price_targets", None))
            if forward_eps == "N/A":
                forward_eps = _extract_forward_eps_from_earnings_estimate(getattr(ticker, "earnings_estimate", None))
            earnings_growth = _format_growth_percentage(
                info.get("earningsGrowth") if info.get("earningsGrowth") is not None else info.get("earningsQuarterlyGrowth")
            )
            short_float_pct = _format_fractional_percent(info.get("shortPercentOfFloat"))
            short_ratio = _format_short_ratio(info.get("shortRatio"))
            analyst_target_price = _format_price(info.get("targetMeanPrice"), currency)
            analyst_recommendation = _map_recommendation(_coerce_finite_float(info.get("recommendationMean")))
            analyst_count = _format_analyst_count(info.get("numberOfAnalystOpinions"))
            held_by_insiders = _format_fractional_percent(info.get("heldPercentInsiders"))
            held_by_institutions = _format_fractional_percent(info.get("heldPercentInstitutions"))
            implied_volatility = _format_fractional_percent(info.get("impliedVolatility"))
            options_summary = collect_options_summary(item.ticker)
            quarterly_financials = _extract_yfinance_quarterly_financials(ticker)
            if earnings_growth == "N/A":
                earnings_growth = _derive_growth_from_quarterly_financials(quarterly_financials)
            upcoming_events = _extract_yfinance_events(item.ticker, info, ticker, run_date)
            if price is not None:
                price_change_7d = _format_period_change(history, price, run_date, 7)
                price_change_30d = _format_period_change(history, price, run_date, 30)
            atr_14d, atr_percent = _calc_atr_display(history, price)
            relative_volume = _calc_relative_volume(info)
            gap_percent = _calc_gap_percent(open_price, previous_close)
            price_vs_sma50 = _calc_price_vs_sma(price, _coerce_finite_float(info.get("fiftyDayAverage")))
            price_vs_sma200 = _calc_price_vs_sma(price, _coerce_finite_float(info.get("twoHundredDayAverage")))
            week52_position = _calc_week52_position(
                price,
                _coerce_finite_float(info.get("fiftyTwoWeekHigh")),
                _coerce_finite_float(info.get("fiftyTwoWeekLow")),
            )
            rs_vs_spy = _calc_rs_vs_benchmark(price_change_30d, benchmark_change_30d)
            providers_used.append("yfinance")
            record_pipeline_event("collector", "info", "data_provider_used", ticker=item.ticker, source="yfinance")
        except Exception as exc:
            record_pipeline_event(
                "collector",
                "warning",
                "ticker_provider_failed",
                ticker=item.ticker,
                source="yfinance",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    if price is None and stooq_ready:
        stooq_price, stooq_change = _fetch_stooq_price_snapshot(item.ticker)
        if stooq_price is not None:
            price = stooq_price
            change_percent = stooq_change
            providers_used.append("stooq")
            record_pipeline_event("collector", "info", "data_provider_used", ticker=item.ticker, source="stooq")

    alpha_bundle: dict[str, Any] = {}
    need_alpha_estimates = forward_eps == "N/A" or earnings_growth == "N/A"
    need_alpha_calendar = _earnings_event_missing_timing(upcoming_events) or not _has_earnings_event(upcoming_events)

    if alpha_ready and (
        need_alpha_calendar
        or _needs_alpha_vantage(
        market_cap=market_cap,
        pe_ratio=pe_ratio,
        eps=eps,
        week52_high=week52_high,
        week52_low=week52_low,
        sma_50=sma_50,
        sma_200=sma_200,
        volume=volume,
        avg_volume_3m=avg_volume_3m,
        price_to_book=price_to_book,
        dividend_yield=dividend_yield,
        forward_eps=forward_eps,
        earnings_growth=earnings_growth,
        quarterly_financials=quarterly_financials,
        upcoming_events=upcoming_events,
    )):
        alpha_bundle = _fetch_alpha_vantage_bundle(
            item.ticker,
            include_estimates=need_alpha_estimates,
            include_calendar=need_alpha_calendar,
        )
        if alpha_bundle:
            providers_used.append("alpha_vantage")
            record_pipeline_event("collector", "info", "data_provider_used", ticker=item.ticker, source="alpha_vantage")

    if alpha_bundle:
        overview = alpha_bundle.get("overview", {})
        market_cap = market_cap if market_cap != "N/A" else _format_large_number(overview.get("MarketCapitalization"))
        pe_ratio = pe_ratio if pe_ratio != "N/A" else _format_ratio(overview.get("PERatio"))
        eps = eps if eps != "N/A" else _format_ratio(overview.get("EPS"))
        week52_high = week52_high if week52_high != "N/A" else _format_ratio(overview.get("52WeekHigh"))
        week52_low = week52_low if week52_low != "N/A" else _format_ratio(overview.get("52WeekLow"))
        sma_50 = sma_50 if sma_50 != "N/A" else _format_ratio(overview.get("50DayMovingAverage"))
        sma_200 = sma_200 if sma_200 != "N/A" else _format_ratio(overview.get("200DayMovingAverage"))
        volume = volume if volume != "N/A" else _format_large_number(overview.get("Volume"))
        avg_volume_3m = avg_volume_3m if avg_volume_3m != "N/A" else _format_large_number(overview.get("AverageVolume"))
        price_to_book = price_to_book if price_to_book != "N/A" else _format_ratio(overview.get("PriceToBookRatio"))
        dividend_yield = dividend_yield if dividend_yield != "N/A" else _format_percent_ratio(overview.get("DividendYield"))
        if forward_eps == "N/A":
            forward_eps = _format_ratio(overview.get("ForwardEPS"))
            if forward_eps == "N/A":
                forward_eps = _derive_forward_eps(price, overview.get("ForwardPE"))
            if forward_eps == "N/A":
                forward_eps = _extract_alpha_forward_eps_from_estimates(alpha_bundle)
        if earnings_growth == "N/A":
            earnings_growth = _format_growth_percentage(overview.get("QuarterlyEarningsGrowthYOY"))
        analyst_target_price = (
            analyst_target_price
            if analyst_target_price != "N/A"
            else _format_price(overview.get("AnalystTargetPrice"), currency)
        )
        quarterly_financials = _merge_quarterly_financials_with_alpha(quarterly_financials, alpha_bundle)
        if earnings_growth == "N/A":
            earnings_growth = _derive_growth_from_quarterly_financials(quarterly_financials)
        if earnings_growth == "N/A":
            earnings_growth = _extract_alpha_growth_from_estimates(alpha_bundle)
        upcoming_events = _merge_alpha_earnings_calendar(item.ticker, upcoming_events, alpha_bundle, run_date)
        if not upcoming_events:
            upcoming_events = _extract_alpha_events(item.ticker, alpha_bundle, run_date)

    if price is None and not providers_used:
        return _fallback_market_data(item, "시장 데이터를 불러오지 못해 기본값을 사용했습니다.")

    summary_note = _build_summary_note(run_date, providers_used)
    return CollectedTickerData(
        ticker=item.ticker,
        name=item.name,
        sector=item.sector,
        price=price,
        change_percent=change_percent,
        currency=currency,
        market_cap=market_cap,
        pe_ratio=pe_ratio,
        summary_note=summary_note,
        eps=eps,
        week52_high=week52_high,
        week52_low=week52_low,
        sma_50=sma_50,
        sma_200=sma_200,
        volume=volume,
        avg_volume_3m=avg_volume_3m,
        price_to_book=price_to_book,
        dividend_yield=dividend_yield,
        forward_eps=forward_eps,
        earnings_growth=earnings_growth,
        short_float_pct=short_float_pct,
        short_ratio=short_ratio,
        analyst_target_price=analyst_target_price,
        analyst_recommendation=analyst_recommendation,
        analyst_count=analyst_count,
        held_by_insiders=held_by_insiders,
        held_by_institutions=held_by_institutions,
        implied_volatility=implied_volatility,
        quarterly_financials=quarterly_financials,
        upcoming_events=upcoming_events,
        price_change_7d=price_change_7d,
        price_change_30d=price_change_30d,
        atr_14d=atr_14d,
        atr_percent=atr_percent,
        relative_volume=relative_volume,
        gap_percent=gap_percent,
        price_vs_sma50=price_vs_sma50,
        price_vs_sma200=price_vs_sma200,
        week52_position=week52_position,
        rs_vs_spy=rs_vs_spy,
        options_summary=options_summary,
    )


def _fallback_market_data(item: WatchlistItem, summary_note: str) -> CollectedTickerData:
    return CollectedTickerData(
        ticker=item.ticker,
        name=item.name,
        sector=item.sector,
        price=None,
        change_percent=None,
        currency="USD",
        market_cap="N/A",
        pe_ratio="N/A",
        summary_note=summary_note,
    )


def _select_price_snapshot(history: object, info: dict[str, Any]) -> tuple[float | None, float | None]:
    close_values = _extract_close_values(history)
    latest_history_close = close_values[-1] if close_values else None
    valid_closes = [value for value in close_values if value is not None]
    live_price = _coerce_finite_float(info.get("regularMarketPrice"))
    if live_price is None:
        live_price = _coerce_finite_float(info.get("currentPrice"))
    previous_close = _coerce_finite_float(info.get("previousClose"))

    if latest_history_close is not None:
        baseline = valid_closes[-2] if len(valid_closes) > 1 else previous_close
        return latest_history_close, _calculate_change_percent(latest_history_close, baseline)

    if live_price is not None:
        baseline = previous_close if previous_close is not None else (valid_closes[-1] if valid_closes else None)
        return live_price, _calculate_change_percent(live_price, baseline)

    if valid_closes:
        latest_valid_close = valid_closes[-1]
        baseline = valid_closes[-2] if len(valid_closes) > 1 else previous_close
        return latest_valid_close, _calculate_change_percent(latest_valid_close, baseline)

    return None, None


def _extract_close_values(history: object) -> list[float | None]:
    return _extract_history_values(history, "Close")


def _fetch_stooq_price_snapshot(ticker: str, *, candidates: list[str] | None = None) -> tuple[float | None, float | None]:
    symbols = candidates or [f"{ticker.lower()}.us", ticker.lower()]
    for symbol in symbols:
        rows = _fetch_stooq_history(symbol)
        if len(rows) < 2:
            continue
        last_date, last_close = rows[-1]
        _ = last_date
        prev_close = rows[-2][1]
        return last_close, _calculate_change_percent(last_close, prev_close)
    return None, None


def _fetch_stooq_history(symbol: str) -> list[tuple[date, float]]:
    url = f"https://stooq.com/q/d/l/?s={parse.quote(symbol)}&i=d"
    try:
        text = _download_text(url)
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "ticker_provider_failed",
            source="stooq",
            error_type=type(exc).__name__,
            error_message=str(exc),
            symbol=symbol,
        )
        return []

    reader = csv.DictReader(io.StringIO(text))
    rows: list[tuple[date, float]] = []
    for row in reader:
        row_date = _parse_iso_date(row.get("Date", ""))
        close_value = _coerce_finite_float(row.get("Close"))
        if row_date is None or close_value is None:
            continue
        rows.append((row_date, close_value))
    return sorted(rows, key=lambda item: item[0])


def _needs_alpha_vantage(**values: Any) -> bool:
    for value in values.values():
        if isinstance(value, list) and not value:
            return True
        if isinstance(value, str) and value == "N/A":
            return True
    return False


def _fetch_alpha_vantage_bundle(
    ticker: str,
    *,
    include_estimates: bool = False,
    include_calendar: bool = False,
) -> dict[str, Any]:
    key = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
    if not key:
        return {}

    if not can_open_tcp_connection("www.alphavantage.co", 443, timeout=5):
        record_pipeline_event("collector", "warning", "alpha_vantage_unreachable", ticker=ticker)
        return {}

    bundle = {
        "overview": _fetch_alpha_vantage_json("OVERVIEW", ticker, key),
        "earnings": _fetch_alpha_vantage_json("EARNINGS", ticker, key),
        "income_statement": _fetch_alpha_vantage_json("INCOME_STATEMENT", ticker, key),
    }
    if include_estimates:
        bundle["earnings_estimates"] = _fetch_alpha_vantage_json("EARNINGS_ESTIMATES", ticker, key)
    if include_calendar:
        bundle["earnings_calendar"] = _fetch_alpha_vantage_csv("EARNINGS_CALENDAR", ticker, key, horizon="12month")
    return bundle


def _fetch_alpha_vantage_json(function_name: str, ticker: str, api_key: str) -> dict[str, Any]:
    global _ALPHA_VANTAGE_LAST_CALL_AT

    cache_key = (function_name, ticker)
    if cache_key in _ALPHA_VANTAGE_CACHE:
        return _ALPHA_VANTAGE_CACHE[cache_key]

    elapsed = time.time() - _ALPHA_VANTAGE_LAST_CALL_AT
    if _ALPHA_VANTAGE_LAST_CALL_AT and elapsed < _ALPHA_VANTAGE_DELAY_SECONDS:
        sleep(_ALPHA_VANTAGE_DELAY_SECONDS - elapsed)

    params = parse.urlencode({"function": function_name, "symbol": ticker, "apikey": api_key})
    url = f"{_ALPHA_VANTAGE_BASE_URL}?{params}"
    try:
        text = _download_text(url)
        payload = json.loads(text)
        if not isinstance(payload, dict):
            return {}
        _ALPHA_VANTAGE_CACHE[cache_key] = payload
        _ALPHA_VANTAGE_LAST_CALL_AT = time.time()
        return payload
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "ticker_provider_failed",
            source="alpha_vantage",
            ticker=ticker,
            function=function_name,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return {}


def _download_text(url: str) -> str:
    with request.urlopen(url, timeout=10) as response:
        return response.read().decode("utf-8")


def _extract_yfinance_quarterly_financials(ticker: Any) -> list[dict[str, str]]:
    statement = getattr(ticker, "quarterly_income_stmt", None)
    if statement is None or getattr(statement, "empty", False):
        return []

    try:
        columns = list(statement.columns)[:8]
    except Exception:
        return []

    earnings_history = _extract_yfinance_earnings_history(ticker)
    reports: list[dict[str, str]] = []
    for column in columns:
        fiscal_date = _coerce_event_date(column).isoformat() if _coerce_event_date(column) else ""
        quarter = _format_quarter(column)
        earnings_entry = _lookup_quarterly_enrichment(earnings_history, fiscal_date, quarter)
        statement_eps = _format_ratio(_statement_value(statement, ["Diluted EPS", "Basic EPS", "DilutedEPS", "BasicEPS"], column))
        reports.append(
            {
                "fiscal_date": fiscal_date,
                "quarter": quarter,
                "revenue": _format_large_number(_statement_value(statement, ["Total Revenue", "Operating Revenue", "TotalRevenue"], column)),
                "operating_income": _format_large_number(_statement_value(statement, ["Operating Income", "OperatingIncome"], column)),
                "eps": statement_eps if statement_eps != "N/A" else str(earnings_entry.get("actual_eps", "N/A")),
                "estimated_eps": str(earnings_entry.get("estimated_eps", "N/A")),
                "surprise_pct": str(earnings_entry.get("surprise_pct", "N/A")),
                "beat_miss": str(earnings_entry.get("beat_miss", "N/A")),
            }
        )
    return reports


def _extract_yfinance_earnings_history(ticker: Any) -> dict[str, dict[str, str]]:
    history = getattr(ticker, "earnings_history", None)
    if history is None or getattr(history, "empty", False):
        return {}

    records = _tabular_records(history)
    normalized: dict[str, dict[str, str]] = {}
    for record in records:
        key_candidates = _quarterly_key_candidates(record)
        estimated_raw = _record_value(record, ["estimatedeps", "epsestimate", "estimate"])
        reported_raw = _record_value(record, ["reportedeps", "epsactual", "actualeps", "eps"])
        surprise_pct_raw = _record_value(record, ["surprisepercentage", "surprisepercent", "surprisepct"])
        estimated_eps = _format_ratio(estimated_raw)
        actual_eps = _format_ratio(reported_raw)
        surprise_pct = _format_surprise_percentage(surprise_pct_raw)
        if surprise_pct == "N/A":
            surprise_pct = _calculate_surprise_percentage(reported_raw, estimated_raw)
        beat_miss = _classify_beat_miss(reported_raw, estimated_raw)
        payload = {
            "actual_eps": actual_eps,
            "estimated_eps": estimated_eps,
            "surprise_pct": surprise_pct,
            "beat_miss": beat_miss,
        }
        for candidate in key_candidates:
            normalized[candidate] = payload
    return normalized


def _fetch_alpha_vantage_csv(function_name: str, ticker: str, api_key: str, **params: str) -> list[dict[str, str]]:
    global _ALPHA_VANTAGE_LAST_CALL_AT

    cache_suffix = json.dumps(params, sort_keys=True)
    cache_key = (function_name, ticker, cache_suffix)
    if cache_key in _ALPHA_VANTAGE_CSV_CACHE:
        return _ALPHA_VANTAGE_CSV_CACHE[cache_key]

    elapsed = time.time() - _ALPHA_VANTAGE_LAST_CALL_AT
    if _ALPHA_VANTAGE_LAST_CALL_AT and elapsed < _ALPHA_VANTAGE_DELAY_SECONDS:
        sleep(_ALPHA_VANTAGE_DELAY_SECONDS - elapsed)

    query_params = {"function": function_name, "symbol": ticker, "apikey": api_key, **params}
    url = f"{_ALPHA_VANTAGE_BASE_URL}?{parse.urlencode(query_params)}"
    try:
        text = _download_text(url).replace("\r", "")
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines or not lines[0].lower().startswith("symbol,"):
            return []
        rows = list(csv.DictReader(io.StringIO("\n".join(lines))))
        _ALPHA_VANTAGE_CSV_CACHE[cache_key] = rows
        _ALPHA_VANTAGE_LAST_CALL_AT = time.time()
        return rows
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "ticker_provider_failed",
            source="alpha_vantage",
            ticker=ticker,
            function=function_name,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return []


def _lookup_quarterly_enrichment(
    earnings_history: dict[str, dict[str, str]] | None,
    fiscal_date: str,
    quarter: str,
) -> dict[str, str]:
    if not earnings_history:
        return {}
    for candidate in (fiscal_date, quarter):
        if candidate and candidate in earnings_history:
            return earnings_history[candidate]
    return {}


def _statement_value(statement: Any, row_names: list[str], column: Any) -> Any:
    for row_name in row_names:
        try:
            if row_name not in statement.index:
                continue
            try:
                return statement.at[row_name, column]
            except Exception:
                return statement.loc[row_name, column]
        except Exception:
            continue
    return None


def _extract_yfinance_events(
    ticker_symbol: str,
    info: dict[str, Any],
    ticker: Any,
    run_date: date,
) -> list[dict[str, str]]:
    earnings_timing = _extract_yfinance_earnings_timing(info)
    raw_events = [
        {"type": "earnings", "label": "실적 발표", "date": info.get("earningsDate"), "timing": earnings_timing},
        {"type": "earnings", "label": "실적 발표", "date": info.get("earningsTimestamp"), "timing": earnings_timing},
        {"type": "earnings", "label": "실적 발표", "date": info.get("earningsTimestampStart"), "timing": earnings_timing},
        {"type": "ex_dividend", "label": "배당락일", "date": info.get("exDividendDate")},
        {"type": "dividend", "label": "배당 지급일", "date": info.get("dividendDate")},
    ]

    calendar = getattr(ticker, "calendar", None)
    raw_events.extend(_extract_calendar_events(calendar))
    return _normalize_upcoming_events(
        raw_events,
        run_date,
        ticker=ticker_symbol,
        source="yfinance",
        calendar_shape=type(calendar).__name__ if calendar is not None else "",
    )


def _extract_alpha_quarterly_financials(bundle: dict[str, Any]) -> list[dict[str, str]]:
    reports = bundle.get("income_statement", {}).get("quarterlyReports", [])
    earnings = bundle.get("earnings", {}).get("quarterlyEarnings", [])
    if not isinstance(reports, list):
        reports = []
    if not isinstance(earnings, list):
        earnings = []

    earnings_by_date = {
        str(entry.get("fiscalDateEnding", "")): entry
        for entry in earnings
        if isinstance(entry, dict)
    }

    normalized: list[dict[str, str]] = []
    for report in reports[:8]:
        if not isinstance(report, dict):
            continue
        fiscal_date = str(report.get("fiscalDateEnding", ""))
        earning_entry = earnings_by_date.get(fiscal_date, {})
        normalized.append(
            {
                "fiscal_date": fiscal_date,
                "quarter": _format_quarter(fiscal_date),
                "revenue": _format_large_number(report.get("totalRevenue")),
                "operating_income": _format_large_number(report.get("operatingIncome")),
                "eps": _format_ratio(earning_entry.get("reportedEPS")),
                "estimated_eps": _format_ratio(earning_entry.get("estimatedEPS")),
                "surprise_pct": _format_surprise_percentage(earning_entry.get("surprisePercentage")),
                "beat_miss": _classify_beat_miss(earning_entry.get("reportedEPS"), earning_entry.get("estimatedEPS")),
            }
        )
    return normalized


def _extract_alpha_events(
    ticker_symbol: str,
    bundle: dict[str, Any],
    run_date: date,
) -> list[dict[str, str]]:
    overview = bundle.get("overview", {}) if isinstance(bundle.get("overview", {}), dict) else {}
    earnings = bundle.get("earnings", {}) if isinstance(bundle.get("earnings", {}), dict) else {}
    quarterly_earnings = earnings.get("quarterlyEarnings", []) if isinstance(earnings, dict) else []

    raw_events = [
        {"type": "ex_dividend", "label": "배당락일", "date": overview.get("ExDividendDate")},
        {"type": "dividend", "label": "배당 지급일", "date": overview.get("DividendDate")},
    ]

    if isinstance(quarterly_earnings, list):
        future_candidates = []
        for entry in quarterly_earnings:
            if not isinstance(entry, dict):
                continue
            candidate_date = entry.get("reportedDate") or entry.get("fiscalDateEnding")
            normalized_date = _coerce_event_date(candidate_date)
            if normalized_date is None or normalized_date < run_date:
                continue
            future_candidates.append(normalized_date)
        if future_candidates:
            raw_events.append({"type": "earnings", "label": "실적 발표", "date": min(future_candidates).isoformat()})

    return _normalize_upcoming_events(raw_events, run_date, ticker=ticker_symbol, source="alpha_vantage")


def _merge_alpha_earnings_calendar(
    ticker_symbol: str,
    existing_events: list[dict[str, str]],
    bundle: dict[str, Any],
    run_date: date,
) -> list[dict[str, str]]:
    calendar_events = _extract_alpha_calendar_events(bundle, run_date, ticker=ticker_symbol)
    if not calendar_events:
        return existing_events

    existing_earnings = [event for event in existing_events if event.get("type") == "earnings"]
    if not existing_earnings:
        return sorted(existing_events + calendar_events, key=lambda item: (item.get("date", ""), item.get("type", "")))

    enriched_earnings = [_merge_earnings_timing(existing, calendar_events) for existing in existing_earnings]
    non_earnings = [event for event in existing_events if event.get("type") != "earnings"]
    return sorted(non_earnings + enriched_earnings, key=lambda item: (item.get("date", ""), item.get("type", "")))


def _extract_alpha_calendar_events(
    bundle: dict[str, Any],
    run_date: date,
    *,
    ticker: str | None = None,
) -> list[dict[str, str]]:
    rows = bundle.get("earnings_calendar", [])
    if not isinstance(rows, list):
        return []

    raw_events: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_events.append(
            {
                "type": "earnings",
                "label": "실적 발표",
                "date": row.get("reportDate") or row.get("date"),
                "timing": _normalize_earnings_timing(row.get("timeOfTheDay") or row.get("reportTime")),
            }
        )

    return _normalize_upcoming_events(raw_events, run_date, ticker=ticker, source="alpha_vantage_calendar")


def _merge_earnings_timing(
    existing_event: dict[str, str],
    calendar_events: list[dict[str, str]],
) -> dict[str, str]:
    if existing_event.get("timing"):
        return existing_event

    existing_date = _coerce_event_date(existing_event.get("date"))
    if existing_date is None:
        return existing_event

    exact_match = next(
        (
            candidate
            for candidate in calendar_events
            if candidate.get("timing") and candidate.get("date") == existing_event.get("date")
        ),
        None,
    )
    if exact_match:
        return {**existing_event, "timing": exact_match.get("timing", "")}

    nearest_match: dict[str, str] | None = None
    nearest_gap: int | None = None
    for candidate in calendar_events:
        if not candidate.get("timing"):
            continue
        candidate_date = _coerce_event_date(candidate.get("date"))
        if candidate_date is None:
            continue
        gap = abs((candidate_date - existing_date).days)
        if gap > 1:
            continue
        if nearest_gap is None or gap < nearest_gap:
            nearest_gap = gap
            nearest_match = candidate

    if nearest_match:
        return {**existing_event, "timing": nearest_match.get("timing", "")}
    return existing_event


def _merge_quarterly_financials_with_alpha(
    existing_rows: list[dict[str, str]],
    bundle: dict[str, Any],
) -> list[dict[str, str]]:
    alpha_rows = _extract_alpha_quarterly_financials(bundle)
    if not existing_rows:
        return alpha_rows
    if not alpha_rows:
        return existing_rows

    alpha_by_key = {
        _quarterly_key(row): row
        for row in alpha_rows
        if _quarterly_key(row)
    }
    merged: list[dict[str, str]] = []
    for row in existing_rows:
        key = _quarterly_key(row)
        alpha_row = alpha_by_key.get(key, {})
        merged.append(
            {
                **row,
                "estimated_eps": str(alpha_row.get("estimated_eps", row.get("estimated_eps", "N/A"))),
                "surprise_pct": str(alpha_row.get("surprise_pct", row.get("surprise_pct", "N/A"))),
                "beat_miss": str(alpha_row.get("beat_miss", row.get("beat_miss", "N/A"))),
            }
        )

    existing_keys = {_quarterly_key(row) for row in existing_rows}
    for row in alpha_rows:
        if _quarterly_key(row) in existing_keys:
            continue
        merged.append(row)
    return merged


def _quarterly_key(row: dict[str, str]) -> str:
    fiscal_date = str(row.get("fiscal_date", "")).strip()
    if fiscal_date:
        return fiscal_date
    return str(row.get("quarter", "")).strip()


def _normalize_upcoming_events(
    raw_events: list[dict[str, Any]],
    run_date: date,
    *,
    ticker: str | None = None,
    source: str | None = None,
    calendar_shape: str = "",
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    parse_failed_count = 0
    past_event_count = 0
    outside_window_count = 0
    duplicate_count = 0
    for raw_event in raw_events:
        event_type = str(raw_event.get("type", "")).strip() or "event"
        label = str(raw_event.get("label", "일정")).strip() or "일정"
        event_date = _coerce_event_date(raw_event.get("date"))
        timing = _normalize_earnings_timing(raw_event.get("timing")) if event_type == "earnings" else ""
        if event_date is None:
            parse_failed_count += 1
            continue
        days_until = (event_date - run_date).days
        max_days = _EARNINGS_LOOKAHEAD_DAYS if event_type == "earnings" else _EVENT_LOOKAHEAD_DAYS
        if days_until < 0 or days_until > max_days:
            if days_until < 0:
                past_event_count += 1
            else:
                outside_window_count += 1
            continue
        dedupe_key = (event_type, event_date.isoformat())
        if dedupe_key in seen:
            duplicate_count += 1
            continue
        seen.add(dedupe_key)
        normalized.append(
            {
                "type": event_type,
                "label": label,
                "date": event_date.isoformat(),
                "days_until": str(days_until),
                "timing": timing,
            }
        )
    normalized = sorted(normalized, key=lambda item: (item["date"], item["type"]))
    normalized, collapsed_earnings_count = _collapse_earnings_event_candidates(normalized)

    if ticker and source:
        record_pipeline_event(
            "collector",
            "info",
            "ticker_events_normalized",
            ticker=ticker,
            source=source,
            raw_event_count=len(raw_events),
            kept_event_count=len(normalized),
            parse_failed_count=parse_failed_count,
            past_event_count=past_event_count,
            outside_window_count=outside_window_count,
            duplicate_count=duplicate_count,
            collapsed_earnings_count=collapsed_earnings_count,
            calendar_shape=calendar_shape,
        )

    return normalized


def _collapse_earnings_event_candidates(events: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    collapsed: list[dict[str, str]] = []
    earliest_earnings: dict[str, str] | None = None
    collapsed_count = 0
    for event in events:
        if event.get("type") != "earnings":
            collapsed.append(event)
            continue
        if earliest_earnings is None:
            earliest_earnings = event
            collapsed.append(event)
            continue
        collapsed_count += 1
    return collapsed, collapsed_count


def _has_earnings_event(events: list[dict[str, str]]) -> bool:
    return any(str(event.get("type", "")).strip() == "earnings" for event in events)


def _earnings_event_missing_timing(events: list[dict[str, str]]) -> bool:
    for event in events:
        if str(event.get("type", "")).strip() != "earnings":
            continue
        return not bool(str(event.get("timing", "")).strip())
    return True


def _coerce_event_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, dict):
        for item in value.values():
            converted = _coerce_event_date(item)
            if converted is not None:
                return converted
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            converted = _coerce_event_date(item)
            if converted is not None:
                return converted
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        if value > 1_000_000_000:
            try:
                timestamp_value = float(value)
                if timestamp_value > 10_000_000_000:
                    timestamp_value /= 1000
                return datetime.utcfromtimestamp(timestamp_value).date()
            except (OverflowError, OSError, ValueError):
                return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text in {"None", "N/A", "0000-00-00"}:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
            except ValueError:
                return None
    return None


def _extract_calendar_events(calendar: Any) -> list[dict[str, Any]]:
    if calendar is None:
        return []

    events: list[dict[str, Any]] = []
    for name, value in _flatten_calendar_entries(calendar):
        event_meta = _event_type_and_label_from_name(name)
        if event_meta is None:
            continue
        event_type, label = event_meta
        events.append({"type": event_type, "label": label, "date": value})
    return events


def _flatten_calendar_entries(value: Any, name_hint: str = "") -> list[tuple[str, Any]]:
    if value is None:
        return []

    flattened: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            flattened.extend(_flatten_calendar_entries(child, f"{name_hint} {key}".strip()))
        return flattened

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _flatten_calendar_entries(to_dict(), name_hint)
        except Exception:
            pass

    index = getattr(value, "index", None)
    loc = getattr(value, "loc", None)
    if index is not None and loc is not None:
        try:
            for key in list(index):
                flattened.extend(_flatten_calendar_entries(loc[key], f"{name_hint} {key}".strip()))
            if flattened:
                return flattened
        except Exception:
            pass

    items = getattr(value, "items", None)
    if callable(items):
        try:
            for key, child in items():
                flattened.extend(_flatten_calendar_entries(child, f"{name_hint} {key}".strip()))
            if flattened:
                return flattened
        except Exception:
            pass

    if isinstance(value, (list, tuple)):
        return [(name_hint, list(value))] if name_hint else []

    return [(name_hint, value)] if name_hint else []


def _event_type_and_label_from_name(name: str) -> tuple[str, str] | None:
    normalized_name = name.strip().lower()
    if not normalized_name:
        return None
    if "earnings" in normalized_name:
        return "earnings", "실적 발표"
    if "exdividend" in normalized_name or "ex-dividend" in normalized_name:
        return "ex_dividend", "배당락일"
    if "dividend" in normalized_name:
        return "dividend", "배당 지급일"
    return None


def _parse_iso_date(raw_value: str) -> date | None:
    try:
        return date.fromisoformat(str(raw_value).strip())
    except ValueError:
        return None


def _build_summary_note(run_date: date, providers_used: list[str]) -> str:
    if not providers_used:
        return f"{run_date.isoformat()} 기준 시장 데이터를 수집하지 못했습니다."
    unique_providers = ", ".join(dict.fromkeys(providers_used))
    return f"{run_date.isoformat()} 기준 {unique_providers} 데이터를 사용해 시장 정보를 정리했습니다."


def _configure_yfinance_cache(yf: Any) -> None:
    cache_dir = Path(".cache") / "yfinance"
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        yf.set_tz_cache_location(str(cache_dir.resolve()))
    except Exception:
        return


def _coerce_finite_float(value: object) -> float | None:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric_value):
        return None
    return numeric_value


def _calculate_change_percent(latest_price: float, baseline_price: float | None) -> float | None:
    if baseline_price is None or baseline_price == 0:
        return None
    return (latest_price - baseline_price) / baseline_price * 100


def _collect_benchmark_change_30d(run_date: date) -> float | None:
    if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
        return None

    symbol, stooq_candidates = _SPY_BENCHMARK
    yfinance_ready = can_open_tcp_connection("query1.finance.yahoo.com", 443)
    stooq_ready = can_open_tcp_connection("stooq.com", 443)

    if yfinance_ready:
        try:
            import yfinance as yf  # type: ignore

            _configure_yfinance_cache(yf)
            ticker = yf.Ticker(symbol)
            history = ticker.history(period="6mo", interval="1d")
            info = getattr(ticker, "info", {}) or {}
            price, _ = _select_price_snapshot(history, info)
            if price is not None:
                return _calculate_history_period_change(history, price, run_date, 30)
        except Exception as exc:
            record_pipeline_event(
                "collector",
                "warning",
                "benchmark_provider_failed",
                source="yfinance",
                benchmark=symbol,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    if stooq_ready:
        try:
            rows: list[tuple[date, float]] = []
            for candidate in stooq_candidates:
                rows = _fetch_stooq_history(candidate)
                if rows:
                    break
            if len(rows) >= 2:
                latest_price = rows[-1][1]
                target_date = run_date - timedelta(days=30)
                anchor_price: float | None = None
                for row_date, close_value in rows:
                    if row_date <= target_date:
                        anchor_price = close_value
                return _calculate_change_percent(latest_price, anchor_price)
        except Exception as exc:
            record_pipeline_event(
                "collector",
                "warning",
                "benchmark_provider_failed",
                source="stooq",
                benchmark=symbol,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    return None


def _extract_yfinance_earnings_timing(info: dict[str, Any]) -> str:
    direct_value = _normalize_earnings_timing(info.get("earningsCallTimeShort") or info.get("earningsCallTime"))
    if direct_value:
        return direct_value

    for key in ("earningsTimestampStart", "earningsTimestamp", "earningsTimestampEnd"):
        timestamp_value = _coerce_finite_float(info.get(key))
        if timestamp_value is None:
            continue
        inferred = _infer_earnings_timing_from_timestamp(timestamp_value)
        if inferred:
            return inferred
    return ""


def _normalize_earnings_timing(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text or text in {"none", "n/a", "nan"}:
        return ""

    normalized = text.replace("_", " ").replace("-", " ")
    compact = "".join(character for character in normalized if character.isalnum())
    if compact in {"bmo", "beforemarketopen", "beforeopen", "premarket", "preopen"}:
        return "BMO"
    if compact in {"amc", "aftermarketclose", "afterclose", "postmarket", "postclose"}:
        return "AMC"
    if "before" in normalized and "open" in normalized:
        return "BMO"
    if "after" in normalized and "close" in normalized:
        return "AMC"
    if "market" in normalized and "open" in normalized:
        return "BMO"
    if "market" in normalized and "close" in normalized:
        return "AMC"
    return text.upper()


def _infer_earnings_timing_from_timestamp(value: float) -> str:
    try:
        timestamp_value = float(value)
        if timestamp_value > 10_000_000_000:
            timestamp_value /= 1000
        hour = datetime.utcfromtimestamp(timestamp_value).hour
    except (OverflowError, OSError, ValueError):
        return ""

    if 11 <= hour <= 15:
        return "BMO"
    if 20 <= hour <= 23:
        return "AMC"
    return ""


def _tabular_records(value: Any) -> list[dict[str, Any]]:
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            records = to_dict("records")
            index_values = list(getattr(value, "index", []))
            normalized_records: list[dict[str, Any]] = []
            for index_value, record in zip(index_values, records, strict=False):
                if isinstance(record, dict):
                    normalized_records.append({"__index__": index_value, **record})
            if normalized_records:
                return normalized_records
        except Exception:
            pass
    return []


def _quarterly_key_candidates(record: dict[str, Any]) -> list[str]:
    date_candidates = [
        record.get("fiscalDateEnding"),
        record.get("quarter"),
        record.get("reportedDate"),
        record.get("date"),
        record.get("__index__"),
    ]
    candidates: list[str] = []
    for raw_value in date_candidates:
        normalized_date = _coerce_event_date(raw_value)
        if normalized_date is not None:
            candidates.append(normalized_date.isoformat())
            candidates.append(_format_quarter(normalized_date.isoformat()))
            continue
        text = str(raw_value or "").strip()
        if text:
            candidates.append(text)
    return [candidate for candidate in dict.fromkeys(candidates) if candidate and candidate != "N/A"]


def _record_value(record: dict[str, Any], field_names: list[str]) -> Any:
    normalized_record = {_normalize_field_name(key): value for key, value in record.items()}
    for field_name in field_names:
        if field_name in normalized_record:
            return normalized_record[field_name]
    return None


def _normalize_field_name(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def _extract_history_values(history: object, column_name: str) -> list[float | None]:
    if getattr(history, "empty", True):
        return []
    try:
        column = history[column_name]
    except Exception:
        return []
    try:
        values = list(column)
    except TypeError:
        values = column if isinstance(column, list) else []
    return [_coerce_finite_float(value) for value in values]


def _calc_atr_display(history: object, current_price: float | None) -> tuple[str, str]:
    atr_value = _calc_atr_14d(history)
    if atr_value is None:
        return "N/A", "N/A"
    atr_percent = _calculate_change_percent(atr_value, current_price)
    if current_price and current_price != 0:
        atr_percent = (atr_value / current_price) * 100
    return f"{atr_value:.2f}", f"{atr_percent:.2f}%" if atr_percent is not None else "N/A"


def _calc_atr_14d(history: object) -> float | None:
    highs = _extract_history_values(history, "High")
    lows = _extract_history_values(history, "Low")
    closes = _extract_history_values(history, "Close")
    if not highs or not lows or not closes:
        return None

    length = min(len(highs), len(lows), len(closes))
    true_ranges: list[float] = []
    previous_close: float | None = None
    for index in range(length):
        high = highs[index]
        low = lows[index]
        close = closes[index]
        if high is None or low is None or close is None:
            previous_close = close if close is not None else previous_close
            continue
        intraday_range = high - low
        if previous_close is None:
            true_range = intraday_range
        else:
            true_range = max(
                intraday_range,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        true_ranges.append(true_range)
        previous_close = close

    if len(true_ranges) < 14:
        return None
    trailing_ranges = true_ranges[-14:]
    return sum(trailing_ranges) / len(trailing_ranges)


def _calc_relative_volume(info: dict[str, Any]) -> str:
    current_volume = _coerce_finite_float(info.get("volume"))
    average_volume = _coerce_finite_float(info.get("averageVolume")) or _coerce_finite_float(info.get("averageVolume10days"))
    if current_volume is None or average_volume is None or average_volume == 0:
        return "N/A"
    return f"{current_volume / average_volume:.2f}x"


def _calc_gap_percent(open_price: float | None, previous_close: float | None) -> str:
    gap = _calculate_change_percent(open_price, previous_close) if open_price is not None else None
    if gap is None:
        return "N/A"
    return f"{gap:+.2f}%"


def _calc_price_vs_sma(price: float | None, sma: float | None) -> str:
    change = _calculate_change_percent(price, sma) if price is not None else None
    if change is None:
        return "N/A"
    return f"{change:+.2f}%"


def _calc_week52_position(price: float | None, week52_high: float | None, week52_low: float | None) -> str:
    if price is None or week52_high is None or week52_low is None or week52_high <= week52_low:
        return "N/A"
    position = ((price - week52_low) / (week52_high - week52_low)) * 100
    return f"{position:.0f}%"


def _calc_rs_vs_benchmark(price_change_30d: str, benchmark_change_30d: float | None) -> str:
    ticker_change = _parse_percent_value(price_change_30d)
    if ticker_change is None or benchmark_change_30d is None:
        return "N/A"
    return f"{(ticker_change - benchmark_change_30d):+.2f}%"


def _parse_percent_value(value: str | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        numeric_value = float(value)
        return numeric_value if math.isfinite(numeric_value) else None
    text = str(value).strip()
    if not text or text == "N/A":
        return None
    if text.endswith("%"):
        text = text[:-1]
    return _coerce_finite_float(text)


def _calculate_history_period_change(history: object, current_price: float, run_date: date, days: int) -> float | None:
    target = run_date - timedelta(days=days)
    if getattr(history, "empty", True):
        return None
    try:
        close_col = history["Close"]
        index = history.index
    except Exception:
        return None

    anchor: float | None = None
    for idx_val, close_val in zip(index, close_col):
        try:
            row_date = idx_val.date() if hasattr(idx_val, "date") else date.fromisoformat(str(idx_val)[:10])
        except Exception:
            continue
        if row_date <= target:
            normalized_close = _coerce_finite_float(close_val)
            if normalized_close is not None:
                anchor = normalized_close
    return _calculate_change_percent(current_price, anchor)


def _format_surprise_percentage(value: object) -> str:
    numeric_value = _coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    return f"{numeric_value:+.2f}%"


def _classify_beat_miss(reported_eps: object, estimated_eps: object) -> str:
    reported = _coerce_finite_float(reported_eps)
    estimated = _coerce_finite_float(estimated_eps)
    if reported is None or estimated is None or estimated == 0:
        return "N/A"
    surprise_percent = ((reported - estimated) / abs(estimated)) * 100
    if surprise_percent >= 5:
        return "beat"
    if surprise_percent <= -5:
        return "miss"
    return "in-line"


def _calculate_surprise_percentage(reported_eps: object, estimated_eps: object) -> str:
    reported = _coerce_finite_float(reported_eps)
    estimated = _coerce_finite_float(estimated_eps)
    if reported is None or estimated is None or estimated == 0:
        return "N/A"
    surprise_percent = ((reported - estimated) / abs(estimated)) * 100
    return f"{surprise_percent:+.2f}%"


def _format_quarter(value: Any) -> str:
    event_date = _coerce_event_date(value)
    if event_date is None:
        return str(value) if value else "N/A"
    quarter = ((event_date.month - 1) // 3) + 1
    return f"{event_date.year}-Q{quarter}"


def _previous_year_quarter_label(quarter: str) -> str | None:
    if not quarter or "-Q" not in quarter:
        return None
    year_text, quarter_text = quarter.split("-Q", 1)
    try:
        return f"{int(year_text) - 1}-Q{int(quarter_text)}"
    except ValueError:
        return None


def _derive_growth_from_quarterly_financials(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "N/A"
    rows_by_quarter = {
        str(row.get("quarter", "")).strip(): row
        for row in rows
        if isinstance(row, dict)
    }
    for row in rows:
        quarter = str(row.get("quarter", "")).strip()
        prior_quarter = _previous_year_quarter_label(quarter)
        if not prior_quarter:
            continue
        prior_row = rows_by_quarter.get(prior_quarter)
        if not prior_row:
            continue
        current_eps = _coerce_finite_float(row.get("eps"))
        prior_eps = _coerce_finite_float(prior_row.get("eps"))
        if current_eps is None or prior_eps is None or prior_eps == 0:
            continue
        growth = ((current_eps - prior_eps) / abs(prior_eps)) * 100
        return f"{growth:+.2f}% YoY"
    return "N/A"


def _format_large_number(value: object) -> str:
    numeric_value = _coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    if numeric_value >= 1_000_000_000_000:
        return f"{numeric_value / 1_000_000_000_000:.2f}T"
    if numeric_value >= 1_000_000_000:
        return f"{numeric_value / 1_000_000_000:.2f}B"
    if numeric_value >= 1_000_000:
        return f"{numeric_value / 1_000_000:.2f}M"
    return f"{numeric_value:,.0f}"


def _format_ratio(value: object) -> str:
    numeric_value = _coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    return f"{numeric_value:.2f}"


def _format_short_ratio(value: object) -> str:
    formatted = _format_ratio(value)
    if formatted == "N/A":
        return formatted
    return f"{formatted}일"


def _format_price(value: object, currency: str) -> str:
    formatted = _format_ratio(value)
    if formatted == "N/A":
        return formatted
    return f"{formatted} {currency}".strip()


def _format_analyst_count(value: object) -> str:
    numeric_value = _coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    return f"{int(numeric_value)}명"


def _map_recommendation(score: float | None) -> str:
    if score is None:
        return "N/A"
    if score <= 1.5:
        return "Strong Buy"
    if score <= 2.5:
        return "Buy"
    if score <= 3.5:
        return "Hold"
    if score <= 4.5:
        return "Sell"
    return "Strong Sell"


def _derive_forward_eps(price: float | None, forward_pe: object) -> str:
    forward_pe_value = _coerce_finite_float(forward_pe)
    if price is None or forward_pe_value is None or forward_pe_value == 0:
        return "N/A"
    return f"{(price / forward_pe_value):.2f}"


def _extract_forward_eps_from_analyst_targets(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, dict):
        return _format_ratio(
            value.get("consensusMeanEps")
            or value.get("meanEps")
            or value.get("targetMeanEps")
        )

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _extract_forward_eps_from_analyst_targets(to_dict())
        except Exception:
            return "N/A"

    return "N/A"


def _extract_forward_eps_from_earnings_estimate(value: Any) -> str:
    records = _tabular_records(value)
    if not records and isinstance(value, dict):
        records = [{"__index__": key, **child} for key, child in value.items() if isinstance(child, dict)]
    if not records:
        return "N/A"

    ranked_records = sorted(records, key=_earnings_estimate_priority)
    for record in ranked_records:
        estimate = _record_value(
            record,
            [
                "avg",
                "average",
                "estimate",
                "epsestimate",
                "consensus",
                "consensuseps",
                "meaneps",
                "consensusmeaneps",
            ],
        )
        formatted = _format_ratio(estimate)
        if formatted != "N/A":
            return formatted
    return "N/A"


def _extract_alpha_forward_eps_from_estimates(bundle: dict[str, Any]) -> str:
    estimates = bundle.get("earnings_estimates", {})
    annual_records = _extract_alpha_estimate_records(estimates, period="annual")
    for record in annual_records:
        formatted = _format_ratio(
            _record_value(
                record,
                [
                    "estimatedeps",
                    "epsestimate",
                    "consensuseps",
                    "meaneps",
                    "averageepsestimate",
                    "epsavg",
                    "epsaverage",
                    "estimate",
                ],
            )
        )
        if formatted != "N/A":
            return formatted

    quarterly_records = _extract_alpha_estimate_records(estimates, period="quarterly")
    quarterly_values: list[float] = []
    for record in quarterly_records[:4]:
        value = _coerce_finite_float(
            _record_value(
                record,
                [
                    "estimatedeps",
                    "epsestimate",
                    "consensuseps",
                    "meaneps",
                    "averageepsestimate",
                    "epsavg",
                    "epsaverage",
                    "estimate",
                ],
            )
        )
        if value is None:
            continue
        quarterly_values.append(value)
    if len(quarterly_values) == 4:
        return f"{sum(quarterly_values):.2f}"
    return "N/A"


def _extract_alpha_growth_from_estimates(bundle: dict[str, Any]) -> str:
    annual_records = _extract_alpha_estimate_records(bundle.get("earnings_estimates", {}), period="annual")
    values: list[float] = []
    for record in annual_records:
        estimate_value = _coerce_finite_float(
            _record_value(
                record,
                [
                    "estimatedeps",
                    "epsestimate",
                    "consensuseps",
                    "meaneps",
                    "averageepsestimate",
                    "epsavg",
                    "epsaverage",
                    "estimate",
                ],
            )
        )
        if estimate_value is None:
            continue
        values.append(estimate_value)
        if len(values) == 2:
            break
    if len(values) < 2 or values[0] == 0:
        return "N/A"
    growth = ((values[1] - values[0]) / abs(values[0])) * 100
    return f"{growth:+.2f}% YoY est"


def _extract_alpha_estimate_records(value: Any, *, period: str) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []

    desired = "annual" if period == "annual" else "quarter"
    candidates: list[dict[str, Any]] = []
    for key, child in value.items():
        if not isinstance(child, list):
            continue
        normalized_key = _normalize_field_name(key)
        if desired == "annual":
            if "annual" not in normalized_key:
                continue
        else:
            if "quarter" not in normalized_key:
                continue
        for row in child:
            if isinstance(row, dict):
                candidates.append(row)

    return sorted(candidates, key=_alpha_estimate_record_sort_key)


def _alpha_estimate_record_sort_key(record: dict[str, Any]) -> tuple[int, str]:
    for field_name in ("fiscalDateEnding", "fiscalYear", "year", "date"):
        raw_value = record.get(field_name)
        normalized_date = _coerce_event_date(raw_value)
        if normalized_date is not None:
            return (0, normalized_date.isoformat())
        text = str(raw_value or "").strip()
        if text:
            return (0, text)
    return (1, "")


def _earnings_estimate_priority(record: dict[str, Any]) -> int:
    label = str(record.get("__index__") or record.get("period") or record.get("date") or "").strip().lower()
    normalized_label = "".join(character for character in label if character.isalnum() or character in {"+", "-"})
    priority_order = [
        "+1y",
        "nextyear",
        "1y",
        "0y",
        "currentyear",
        "+1q",
        "nextquarter",
        "1q",
        "0q",
        "currentquarter",
    ]
    for index, token in enumerate(priority_order):
        if token and token in normalized_label:
            return index
    return len(priority_order)


def _format_period_change(history: object, current_price: float, run_date: date, days: int) -> str:
    period_change = _calculate_history_period_change(history, current_price, run_date, days)
    if period_change is None:
        return "N/A"
    return f"{period_change:+.2f}%"


def _format_percent_ratio(value: object) -> str:
    numeric_value = _coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    # Some providers return ratios as decimals (0.0041 => 0.41%),
    # while others already return percentage points (0.41 => 0.41%).
    if abs(numeric_value) < 0.2:
        numeric_value *= 100
    return f"{numeric_value:.2f}%"


def _format_fractional_percent(value: object) -> str:
    numeric_value = _coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    return f"{numeric_value * 100:.2f}%"


def _format_growth_percentage(value: object) -> str:
    numeric_value = _coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    if abs(numeric_value) < 1:
        numeric_value *= 100
    return f"{numeric_value:+.2f}% YoY"
