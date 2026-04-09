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
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

_ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
_ALPHA_VANTAGE_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
_ALPHA_VANTAGE_LAST_CALL_AT = 0.0
_ALPHA_VANTAGE_DELAY_SECONDS = 12.0
_MARKET_INDICES = [
    ("^GSPC", "S&P 500", ["^spx", "^spx.us", "spx.us"]),
    ("^NDX", "NASDAQ 100", ["^ndx", "^ndx.us", "ndx.us"]),
]
_EVENT_LOOKAHEAD_DAYS = 14


def collect_market_data(
    watchlist: list[WatchlistItem],
    run_date: date,
) -> dict[str, CollectedTickerData]:
    results: dict[str, CollectedTickerData] = {}
    for item in watchlist:
        results[item.ticker] = _collect_single_ticker(item, run_date)
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
    quarterly_financials: list[dict[str, str]] = []
    upcoming_events: list[dict[str, str]] = []

    price_change_7d = "N/A"
    price_change_30d = "N/A"

    if yfinance_ready:
        try:
            import yfinance as yf  # type: ignore

            _configure_yfinance_cache(yf)
            ticker = yf.Ticker(item.ticker)
            history = ticker.history(period="6mo", interval="1d")
            info = getattr(ticker, "info", {}) or {}
            price, change_percent = _select_price_snapshot(history, info)
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
            quarterly_financials = _extract_yfinance_quarterly_financials(ticker)
            upcoming_events = _extract_yfinance_events(item.ticker, info, ticker, run_date)
            if price is not None:
                price_change_7d = _format_period_change(history, price, run_date, 7)
                price_change_30d = _format_period_change(history, price, run_date, 30)
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
    if alpha_ready and _needs_alpha_vantage(
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
        quarterly_financials=quarterly_financials,
        upcoming_events=upcoming_events,
    ):
        alpha_bundle = _fetch_alpha_vantage_bundle(item.ticker)
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
        if not quarterly_financials:
            quarterly_financials = _extract_alpha_quarterly_financials(alpha_bundle)
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
        quarterly_financials=quarterly_financials,
        upcoming_events=upcoming_events,
        price_change_7d=price_change_7d,
        price_change_30d=price_change_30d,
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
    if getattr(history, "empty", True):
        return []
    try:
        if "Close" not in history:
            return []
        raw_values = list(history["Close"])
    except Exception:
        return []
    return [_coerce_finite_float(value) for value in raw_values]


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


def _fetch_alpha_vantage_bundle(ticker: str) -> dict[str, Any]:
    key = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
    if not key:
        return {}

    return {
        "overview": _fetch_alpha_vantage_json("OVERVIEW", ticker, key),
        "earnings": _fetch_alpha_vantage_json("EARNINGS", ticker, key),
        "income_statement": _fetch_alpha_vantage_json("INCOME_STATEMENT", ticker, key),
    }


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
    with request.urlopen(url, timeout=15) as response:
        return response.read().decode("utf-8")


def _extract_yfinance_quarterly_financials(ticker: Any) -> list[dict[str, str]]:
    statement = getattr(ticker, "quarterly_income_stmt", None)
    if statement is None or getattr(statement, "empty", False):
        return []

    try:
        columns = list(statement.columns)[:8]
    except Exception:
        return []

    reports: list[dict[str, str]] = []
    for column in columns:
        reports.append(
            {
                "quarter": _format_quarter(column),
                "revenue": _format_large_number(_statement_value(statement, ["Total Revenue", "Operating Revenue", "TotalRevenue"], column)),
                "operating_income": _format_large_number(_statement_value(statement, ["Operating Income", "OperatingIncome"], column)),
                "eps": _format_ratio(_statement_value(statement, ["Diluted EPS", "Basic EPS", "DilutedEPS", "BasicEPS"], column)),
            }
        )
    return reports


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
    raw_events = [
        {"type": "earnings", "label": "실적 발표", "date": info.get("earningsDate")},
        {"type": "earnings", "label": "실적 발표", "date": info.get("earningsTimestamp")},
        {"type": "earnings", "label": "실적 발표", "date": info.get("earningsTimestampStart")},
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
                "quarter": _format_quarter(fiscal_date),
                "revenue": _format_large_number(report.get("totalRevenue")),
                "operating_income": _format_large_number(report.get("operatingIncome")),
                "eps": _format_ratio(earning_entry.get("reportedEPS")),
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
        if event_date is None:
            parse_failed_count += 1
            continue
        days_until = (event_date - run_date).days
        if days_until < 0 or days_until > _EVENT_LOOKAHEAD_DAYS:
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
            }
        )
    normalized = sorted(normalized, key=lambda item: (item["date"], item["type"]))

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
            calendar_shape=calendar_shape,
        )

    return normalized


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


def _format_quarter(value: Any) -> str:
    event_date = _coerce_event_date(value)
    if event_date is None:
        return str(value) if value else "N/A"
    quarter = ((event_date.month - 1) // 3) + 1
    return f"{event_date.year}-Q{quarter}"


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


def _format_period_change(history: object, current_price: float, run_date: date, days: int) -> str:
    target = run_date - timedelta(days=days)
    if getattr(history, "empty", True):
        return "N/A"
    try:
        close_col = history["Close"]
        index = history.index
    except Exception:
        return "N/A"
    anchor: float | None = None
    for idx_val, close_val in zip(index, close_col):
        try:
            row_date = idx_val.date() if hasattr(idx_val, "date") else date.fromisoformat(str(idx_val)[:10])
        except Exception:
            continue
        if row_date <= target:
            c = _coerce_finite_float(close_val)
            if c is not None:
                anchor = c
    if anchor is None or anchor == 0:
        return "N/A"
    return f"{(current_price - anchor) / anchor * 100:+.2f}%"


def _format_percent_ratio(value: object) -> str:
    numeric_value = _coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    # Some providers return ratios as decimals (0.0041 => 0.41%),
    # while others already return percentage points (0.41 => 0.41%).
    if abs(numeric_value) < 0.2:
        numeric_value *= 100
    return f"{numeric_value:.2f}%"
