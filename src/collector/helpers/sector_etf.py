from __future__ import annotations

from datetime import date
from typing import Any, Callable, Mapping

from src.collector.helpers.yfinance_helpers import _select_price_snapshot
from src.collector.technicals import _calc_rs_vs_benchmark, _format_period_change
from src.utils.config import load_sector_etf_map


def calculate_rs_vs_sector_etf(
    ticker_history: Any,
    sector: str,
    run_date: date,
    *,
    get_etf_history: Callable[[str], Any],
    sector_etf_map: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    normalized_sector = str(sector or '').strip()
    if not normalized_sector:
        return 'N/A', ''

    mapping = dict(sector_etf_map or load_sector_etf_map())
    etf_symbol = mapping.get(normalized_sector, '').strip().upper()
    if not etf_symbol:
        return 'N/A', ''

    ticker_price, _ = _select_price_snapshot(ticker_history, {})
    if ticker_price is None:
        return 'N/A', etf_symbol

    ticker_change_30d = _format_period_change(ticker_history, ticker_price, run_date, 30)
    etf_history = get_etf_history(etf_symbol)
    etf_price, _ = _select_price_snapshot(etf_history, {})
    if etf_price is None:
        return 'N/A', etf_symbol

    etf_change_30d = _format_period_change(etf_history, etf_price, run_date, 30)
    benchmark_change = _parse_percent_value(etf_change_30d)
    return _calc_rs_vs_benchmark(ticker_change_30d, benchmark_change), etf_symbol


def _parse_percent_value(value: str | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text == 'N/A':
        return None
    if text.endswith('%'):
        text = text[:-1]
    try:
        return float(text.replace(',', ''))
    except ValueError:
        return None
