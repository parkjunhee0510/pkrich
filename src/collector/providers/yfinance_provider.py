"""YFinance DataProvider — first concrete provider in the plugin architecture.

Responsibilities (yfinance-native data only):
  * price / change_percent / currency
  * fundamentals: market_cap, pe_ratio, eps, forward_eps, earnings_growth,
    price_to_book, dividend_yield, analyst_* targets & recommendations,
    short float, insider/institution ownership, implied_volatility
  * technicals & price action: SMA50/200, 52-week high/low + position,
    ATR(14), relative volume, gap %, price vs SMA, RS vs benchmark
  * quarterly financials
  * upcoming events (earnings / dividends)
  * historical price rows (6mo daily)
  * OHLCV snapshot for today

Anything outside this scope (FMP, Finnhub, Polygon, Alpha Vantage, SEC) is
delegated to other providers. This provider NEVER calls those services,
preserving the one-concern-per-provider contract.

Migration note (Phase 1-0e Step 2):
    This provider intentionally delegates to existing helpers in
    `src.collector.price` so we don't duplicate 1,900 lines of extraction
    logic. Step 5 of the migration will move those helpers into this file
    (or a dedicated `yfinance_impl.py`) and delete them from price.py.
"""
from __future__ import annotations

import logging
from typing import Any

from src.collector import price as price_legacy
from src.collector.helpers.yfinance_helpers import (
    _configure_yfinance_cache,
    _select_price_snapshot,
    _extract_latest_ohlcv,
    _extract_historical_price_rows,
    _extract_yfinance_quarterly_financials,
    _extract_yfinance_events,
)
from src.collector.helpers.earnings import (
    _derive_growth_from_quarterly_financials,
    _extract_forward_eps_from_analyst_targets,
    _extract_forward_eps_from_earnings_estimate,
)
from src.collector.base import (
    CollectionContext,
    DataProvider,
    PartialTickerData,
    ProviderResult,
    RateLimit,
)
from src.collector.helpers.formatters import (
    coerce_finite_float,
    derive_forward_eps,
    format_analyst_count,
    format_fractional_percent,
    format_growth_percentage,
    format_large_number,
    format_percent_ratio,
    format_price,
    format_ratio,
    format_short_ratio,
    map_recommendation,
)
from src.collector.options import collect_options_summary
from src.collector.technicals import (
    compute_technical_indicators,
    _calc_atr_display,
    _calc_gap_percent,
    _calc_price_vs_sma,
    _calc_relative_volume,
    _calc_rs_vs_benchmark,
    _calc_week52_position,
    _format_period_change,
)
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)

_YF_HOST = "query1.finance.yahoo.com"
_YF_PORT = 443


class YFinanceProvider(DataProvider):
    """Priority-1 yfinance source covering the bulk of daily ticker metrics.

    The provider reuses the private helpers in `src.collector.price` to
    avoid re-implementing formatting/normalization logic that is already
    well tested. As we peel off more providers, those helpers will move
    into this module and price.py will shrink toward deletion.

    Args:
        benchmark_change_30d: 30-day % change of the RS benchmark (SPY/^GSPC).
            Supplied by the caller (usually CollectionOrchestrator's hook
            point, which pre-fetches it once per run). Optional — missing
            benchmark simply leaves `rs_vs_spy` as 'N/A'.
    """

    name = "yfinance"
    provides = {
        "price",
        "fundamentals",
        "technicals",
        "quarterly_financials",
        "upcoming_events",
        "historical_prices",
        "options",
    }
    priority = 1
    rate_limit = RateLimit(calls_per_minute=60, burst=20)

    def __init__(self, benchmark_change_30d: float | None = None) -> None:
        self._benchmark_change_30d = benchmark_change_30d
        # Cached `yfinance` module handle — imported lazily so the pipeline
        # doesn't crash in environments where the package isn't installed.
        self._yf_module: Any | None = None

    # ---------------------------------------------------------------
    # DataProvider contract
    # ---------------------------------------------------------------
    def is_available(self) -> bool:
        """Cheap availability probe: external fetch flag + TCP reachability.

        We don't import yfinance here — that import cost is paid lazily
        on the first collect(). This keeps `is_available()` side-effect
        free for registry diagnostics.
        """
        if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
            return False
        return can_open_tcp_connection(_YF_HOST, _YF_PORT)

    def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
        """Fetch all yfinance-native fields for one ticker. Never raises."""
        try:
            yf = self._get_yfinance_module()
            if yf is None:
                return ProviderResult.failure(self.name, reason="yfinance_import_failed")

            fields = self._collect_fields(yf, ticker, ctx)
            has_price = fields.get("price") is not None
            has_market_cap = fields.get("market_cap", "N/A") not in ("N/A", "")
            if not has_price and not has_market_cap:
                # No usable data — report failure so orchestrator can fallback.
                return ProviderResult.failure(self.name, reason="empty_snapshot")

            record_pipeline_event(
                "collector", "info", "data_provider_used",
                ticker=ticker, source=self.name,
            )
            return ProviderResult.success(
                self.name,
                PartialTickerData(ticker=ticker, fields=fields),
            )
        except Exception as err:  # noqa: BLE001 — must not raise
            logger.exception("yfinance provider failed for %s", ticker)
            record_pipeline_event(
                "collector", "warning", "ticker_provider_failed",
                ticker=ticker, source=self.name,
                error_type=type(err).__name__, error_message=str(err),
            )
            return ProviderResult.failure(self.name, reason=f"exception:{err}")

    # ---------------------------------------------------------------
    # internals
    # ---------------------------------------------------------------
    def _get_yfinance_module(self) -> Any | None:
        if self._yf_module is not None:
            return self._yf_module
        try:
            import yfinance as yf  # type: ignore

            _configure_yfinance_cache(yf)
            self._yf_module = yf
            return yf
        except Exception as err:  # noqa: BLE001
            logger.warning("yfinance import failed: %s", err)
            return None

    def _collect_fields(
        self,
        yf: Any,
        ticker_symbol: str,
        ctx: CollectionContext,
    ) -> dict[str, Any]:
        """Assemble the PartialTickerData.fields dict from yfinance."""
        t = yf.Ticker(ticker_symbol)
        history = t.history(period="6mo", interval="1d")
        info = getattr(t, "info", {}) or {}

        price, change_percent = _select_price_snapshot(history, info)
        open_price = coerce_finite_float(info.get("regularMarketOpen"))
        previous_close = coerce_finite_float(info.get("previousClose"))
        currency = str(info.get("currency", "USD") or "USD")

        # Basic fundamentals.
        market_cap = format_large_number(info.get("marketCap"))
        pe_ratio = format_ratio(info.get("trailingPE"))
        eps = format_ratio(info.get("trailingEps"))
        price_to_book = format_ratio(info.get("priceToBook"))
        dividend_yield = format_percent_ratio(info.get("dividendYield"))

        # Forward EPS with graceful fallback chain.
        forward_eps = format_ratio(
            info.get("forwardEps") or info.get("epsForward")
        )
        if forward_eps == "N/A":
            forward_eps = derive_forward_eps(price, info.get("forwardPE"))
        if forward_eps == "N/A":
            forward_eps = _extract_forward_eps_from_analyst_targets(
                getattr(t, "analyst_price_targets", None)
            )
        if forward_eps == "N/A":
            forward_eps = _extract_forward_eps_from_earnings_estimate(
                getattr(t, "earnings_estimate", None)
            )

        earnings_growth = format_growth_percentage(
            info.get("earningsGrowth")
            if info.get("earningsGrowth") is not None
            else info.get("earningsQuarterlyGrowth")
        )

        # Ranges & moving averages.
        week52_high = format_ratio(info.get("fiftyTwoWeekHigh"))
        week52_low = format_ratio(info.get("fiftyTwoWeekLow"))
        sma_50 = format_ratio(info.get("fiftyDayAverage"))
        sma_200 = format_ratio(info.get("twoHundredDayAverage"))
        volume = format_large_number(info.get("volume"))
        avg_volume_3m = format_large_number(info.get("averageVolume"))

        # Positioning (short / analyst / ownership / IV).
        short_float_pct = format_fractional_percent(info.get("shortPercentOfFloat"))
        short_ratio = format_short_ratio(info.get("shortRatio"))
        analyst_target_price = format_price(info.get("targetMeanPrice"), currency)
        analyst_recommendation = map_recommendation(
            coerce_finite_float(info.get("recommendationMean"))
        )
        analyst_count = format_analyst_count(info.get("numberOfAnalystOpinions"))
        held_by_insiders = format_fractional_percent(info.get("heldPercentInsiders"))
        held_by_institutions = format_fractional_percent(info.get("heldPercentInstitutions"))
        implied_volatility = format_fractional_percent(info.get("impliedVolatility"))

        # Derived price-action indicators.
        price_change_7d = price_change_30d = "N/A"
        if price is not None:
            price_change_7d = _format_period_change(history, price, ctx.run_date, 7)
            price_change_30d = _format_period_change(history, price, ctx.run_date, 30)

        atr_14d, atr_percent = _calc_atr_display(history, price)
        relative_volume = _calc_relative_volume(info)
        gap_percent = _calc_gap_percent(open_price, previous_close)
        price_vs_sma50 = _calc_price_vs_sma(
            price, coerce_finite_float(info.get("fiftyDayAverage"))
        )
        price_vs_sma200 = _calc_price_vs_sma(
            price, coerce_finite_float(info.get("twoHundredDayAverage"))
        )
        week52_position = _calc_week52_position(
            price,
            coerce_finite_float(info.get("fiftyTwoWeekHigh")),
            coerce_finite_float(info.get("fiftyTwoWeekLow")),
        )
        rs_vs_spy = _calc_rs_vs_benchmark(
            price_change_30d, self._benchmark_change_30d,
        )

        # Aggregate & quarterly data.
        quarterly_financials = _extract_yfinance_quarterly_financials(t)
        if earnings_growth == "N/A":
            earnings_growth = _derive_growth_from_quarterly_financials(quarterly_financials)
        upcoming_events = _extract_yfinance_events(
            ticker_symbol, info, t, ctx.run_date,
        )

        ohlcv = _extract_latest_ohlcv(history, price, open_price, volume)
        historical_prices = _extract_historical_price_rows(
            history, ticker_symbol, currency,
        )
        technical_indicators = compute_technical_indicators(history)

        # Options summary belongs to yfinance (it uses yfinance under the hood).
        try:
            options_summary = collect_options_summary(ticker_symbol)
        except Exception:  # noqa: BLE001
            options_summary = {}

        return {
            "price": price,
            "change_percent": change_percent,
            "currency": currency,
            "market_cap": market_cap,
            "pe_ratio": pe_ratio,
            "eps": eps,
            "week52_high": week52_high,
            "week52_low": week52_low,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "volume": volume,
            "avg_volume_3m": avg_volume_3m,
            "price_to_book": price_to_book,
            "dividend_yield": dividend_yield,
            "forward_eps": forward_eps,
            "earnings_growth": earnings_growth,
            "short_float_pct": short_float_pct,
            "short_ratio": short_ratio,
            "analyst_target_price": analyst_target_price,
            "analyst_recommendation": analyst_recommendation,
            "analyst_count": analyst_count,
            "held_by_insiders": held_by_insiders,
            "held_by_institutions": held_by_institutions,
            "implied_volatility": implied_volatility,
            "quarterly_financials": quarterly_financials,
            "upcoming_events": upcoming_events,
            "price_change_7d": price_change_7d,
            "price_change_30d": price_change_30d,
            "atr_14d": atr_14d,
            "atr_percent": atr_percent,
            "relative_volume": relative_volume,
            "gap_percent": gap_percent,
            "price_vs_sma50": price_vs_sma50,
            "price_vs_sma200": price_vs_sma200,
            "week52_position": week52_position,
            "rs_vs_spy": rs_vs_spy,
            "options_summary": options_summary,
            "open_price": ohlcv.get("open", "N/A") if ohlcv else "N/A",
            "high_price": ohlcv.get("high", "N/A") if ohlcv else "N/A",
            "low_price": ohlcv.get("low", "N/A") if ohlcv else "N/A",
            "close_price": ohlcv.get("close", "N/A") if ohlcv else "N/A",
            "day_volume": ohlcv.get("volume", "N/A") if ohlcv else "N/A",
            "technical_indicators": technical_indicators,
            "historical_prices": historical_prices,
        }


__all__ = ["YFinanceProvider"]
