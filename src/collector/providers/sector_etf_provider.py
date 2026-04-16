"""Sector ETF relative-strength provider.

Computes 30-day relative strength of a ticker versus its mapped sector ETF.
The provider is intentionally narrow:

* provides: {"sector_rs"}
* priority: 1
* source: yfinance history only

It never reaches into analyzer/output and only emits one field:
`rs_vs_sector_etf`.
"""
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
from src.collector.helpers.sector_etf import calculate_rs_vs_sector_etf
from src.collector.helpers.yfinance_helpers import _configure_yfinance_cache
from src.utils.config import load_sector_etf_map
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)

_YF_HOST = "query1.finance.yahoo.com"
_YF_PORT = 443


class SectorEtfProvider(DataProvider):
    name = "sector_etf"
    provides = {"sector_rs"}
    priority = 1
    rate_limit = RateLimit(calls_per_minute=30, burst=10)

    def __init__(self) -> None:
        self._yf_module: Any | None = None
        self._sector_etf_map = load_sector_etf_map()
        self._etf_history_cache: dict[str, Any] = {}

    def is_available(self) -> bool:
        if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
            return False
        return can_open_tcp_connection(_YF_HOST, _YF_PORT)

    def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
        sector = ctx.watchlist_item.sector
        if not sector or sector not in self._sector_etf_map:
            return ProviderResult.failure(self.name, reason="no_sector_etf_mapping")

        try:
            yf = self._get_yfinance_module()
            if yf is None:
                return ProviderResult.failure(self.name, reason="yfinance_import_failed")

            ticker_history = yf.Ticker(ticker).history(period="6mo", interval="1d")
            rs_vs_sector_etf, etf_symbol = calculate_rs_vs_sector_etf(
                ticker_history,
                sector,
                ctx.run_date,
                get_etf_history=lambda symbol: self._get_etf_history(yf, symbol),
                sector_etf_map=self._sector_etf_map,
            )
            if rs_vs_sector_etf == "N/A":
                return ProviderResult.failure(self.name, reason=f"sector_rs_unavailable:{etf_symbol or 'unknown'}")

            record_pipeline_event(
                "collector",
                "info",
                "data_provider_used",
                ticker=ticker,
                source=self.name,
                sector=sector,
                sector_etf=etf_symbol,
            )
            return ProviderResult.success(
                self.name,
                PartialTickerData(
                    ticker=ticker,
                    fields={"rs_vs_sector_etf": rs_vs_sector_etf},
                ),
            )
        except Exception as err:  # noqa: BLE001
            logger.exception("sector ETF provider failed for %s", ticker)
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

    def _get_yfinance_module(self) -> Any | None:
        if self._yf_module is not None:
            return self._yf_module
        try:
            import yfinance as yf  # type: ignore

            _configure_yfinance_cache(yf)
            self._yf_module = yf
            return yf
        except Exception as err:  # noqa: BLE001
            logger.warning("yfinance import failed in sector ETF provider: %s", err)
            return None

    def _get_etf_history(self, yf: Any, symbol: str) -> Any:
        cached = self._etf_history_cache.get(symbol)
        if cached is not None:
            return cached
        history = yf.Ticker(symbol).history(period="6mo", interval="1d")
        self._etf_history_cache[symbol] = history
        return history


__all__ = ["SectorEtfProvider"]
