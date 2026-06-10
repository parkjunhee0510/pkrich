from __future__ import annotations

import logging
from typing import Any

from src.collector.base import (
    CollectionContext,
    DataProvider,
    PartialTickerData,
    ProviderResult,
    RateLimit,
)
from src.collector.providers.toss_invest_client import TossInvestClient
from src.utils.env import is_env_flag_enabled
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)


class TossInvestProvider(DataProvider):
    """Read-only Toss Invest market-data provider."""

    name = "toss_invest"
    provides = {"price", "historical_prices", "fundamentals", "technicals", "upcoming_events"}
    priority = 2
    rate_limit = RateLimit(calls_per_minute=60, burst=20)

    def __init__(self, *, client: TossInvestClient | None = None) -> None:
        self._client = client

    def is_available(self) -> bool:
        if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
            return False
        client = self._client or TossInvestClient()
        return bool(getattr(client, "is_configured", False))

    def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
        client = self._client or TossInvestClient()
        try:
            fields = self._collect_fields(client, ticker, ctx)
            if not _has_any_value(fields):
                return ProviderResult.failure(self.name, reason="empty_response")

            record_pipeline_event(
                "collector",
                "info",
                "data_provider_used",
                ticker=ticker,
                source=self.name,
            )
            return ProviderResult.success(
                self.name,
                PartialTickerData(ticker=ticker, fields=fields),
            )
        except Exception as err:  # noqa: BLE001
            logger.exception("toss invest provider failed for %s", ticker)
            record_pipeline_event(
                "collector",
                "warning",
                "ticker_provider_failed",
                ticker=ticker,
                source=self.name,
                error_type=type(err).__name__,
                error_message=str(err),
            )
            return ProviderResult.failure(self.name, reason=f"exception:{err}")

    def _collect_fields(
        self,
        client: TossInvestClient,
        ticker: str,
        ctx: CollectionContext,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        normalized_ticker = _normalize_ticker(ticker)

        price_payload = client.get_prices([normalized_ticker])
        price_row = _find_symbol_row(price_payload.get("result"), normalized_ticker)
        fields.update(_price_fields(price_row))

        candle_payload = _safe_dict(client.get_candles, normalized_ticker, interval="1d", count=60, adjusted=True)
        candles = _extract_candles(candle_payload)
        fields.update(_candle_fields(candles))

        stock_payload = _safe_dict(client.get_stocks, [normalized_ticker])
        stock_row = _find_symbol_row(stock_payload.get("result"), normalized_ticker)
        fields.update(_stock_fields(stock_row))

        warning_payload = _safe_dict(client.get_stock_warnings, normalized_ticker)
        warnings = _extract_list(warning_payload.get("result"))
        if warnings:
            fields["upcoming_events"] = _warning_events(warnings, ctx)

        return fields


def _price_fields(row: dict[str, Any]) -> dict[str, Any]:
    price = _optional_float(row.get("lastPrice"))
    fields: dict[str, Any] = {}
    if price is not None:
        fields["price"] = price
    currency = str(row.get("currency") or "").strip().upper()
    if currency:
        fields["currency"] = currency
    return fields


def _candle_fields(candles: list[dict[str, Any]]) -> dict[str, Any]:
    if not candles:
        return {}

    latest = candles[0]
    fields: dict[str, Any] = {
        "historical_prices": [_historical_price_row(candle) for candle in candles],
    }
    _copy_candle_value(fields, "open_price", latest, "openPrice")
    _copy_candle_value(fields, "high_price", latest, "highPrice")
    _copy_candle_value(fields, "low_price", latest, "lowPrice")
    _copy_candle_value(fields, "close_price", latest, "closePrice")
    _copy_candle_value(fields, "day_volume", latest, "volume")
    _copy_candle_value(fields, "volume", latest, "volume")

    if len(candles) >= 2:
        latest_close = _optional_float(candles[0].get("closePrice"))
        previous_close = _optional_float(candles[1].get("closePrice"))
        if latest_close is not None and previous_close not in (None, 0.0):
            fields["change_percent"] = round(((latest_close - previous_close) / previous_close) * 100, 2)

    return fields


def _stock_fields(row: dict[str, Any]) -> dict[str, Any]:
    if not row:
        return {}
    metrics = {
        "toss_symbol": str(row.get("symbol") or "").strip(),
        "toss_market": str(row.get("market") or "").strip(),
        "toss_security_type": str(row.get("securityType") or "").strip(),
        "toss_status": str(row.get("status") or "").strip(),
        "isin_code": str(row.get("isinCode") or "").strip(),
        "shares_outstanding": str(row.get("sharesOutstanding") or "").strip(),
    }
    metrics = {key: value for key, value in metrics.items() if value}

    fields: dict[str, Any] = {}
    name = str(row.get("englishName") or row.get("name") or "").strip()
    if name:
        fields["name"] = name
    currency = str(row.get("currency") or "").strip().upper()
    if currency:
        fields["currency"] = currency
    if metrics:
        fields["fundamental_metrics"] = metrics
    return fields


def _warning_events(warnings: list[dict[str, Any]], ctx: CollectionContext) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for warning in warnings:
        warning_type = str(warning.get("warningType") or "").strip()
        if not warning_type:
            continue
        event = {
            "type": "stock_warning",
            "label": warning_type,
            "date": str(warning.get("startDate") or ctx.run_date.isoformat()),
            "source": "toss_invest",
            "details": str(warning.get("exchange") or "").strip(),
        }
        end_date = str(warning.get("endDate") or "").strip()
        if end_date:
            event["end_date"] = end_date
        events.append(event)
    return events


def _extract_candles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result")
    if not isinstance(result, dict):
        return []
    return _extract_list(result.get("candles"))


def _find_symbol_row(raw: object, ticker: str) -> dict[str, Any]:
    normalized_ticker = _normalize_ticker(ticker)
    for row in _extract_list(raw):
        if _normalize_ticker(str(row.get("symbol") or "")) == normalized_ticker:
            return row
    return {}


def _extract_list(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _copy_candle_value(
    fields: dict[str, Any],
    field_name: str,
    candle: dict[str, Any],
    source_name: str,
) -> None:
    value = str(candle.get(source_name) or "").strip()
    if value:
        fields[field_name] = value


def _historical_price_row(candle: dict[str, Any]) -> dict[str, str]:
    timestamp = str(candle.get("timestamp") or "").strip()
    return {
        "date": timestamp[:10],
        "open": str(candle.get("openPrice") or "").strip(),
        "high": str(candle.get("highPrice") or "").strip(),
        "low": str(candle.get("lowPrice") or "").strip(),
        "close": str(candle.get("closePrice") or "").strip(),
        "volume": str(candle.get("volume") or "").strip(),
    }


def _safe_dict(fn, *args, **kwargs) -> dict[str, Any]:
    try:
        result = fn(*args, **kwargs)
    except Exception:  # noqa: BLE001
        return {}
    return result if isinstance(result, dict) else {}


def _has_any_value(fields: dict[str, Any]) -> bool:
    for value in fields.values():
        if value in (None, "", "N/A"):
            continue
        if isinstance(value, (dict, list)) and not value:
            continue
        return True
    return False


def _optional_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_ticker(ticker: str) -> str:
    return str(ticker or "").strip().upper()


__all__ = ["TossInvestProvider"]
