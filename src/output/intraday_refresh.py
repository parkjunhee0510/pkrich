from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from src.types import CollectedTickerData, PortfolioSummary
from src.utils.datastore import get_datastore


def write_intraday_refresh_outputs(
    collected: dict[str, CollectedTickerData],
    run_date,
    *,
    market_overview: list[dict[str, str]] | None = None,
    macro_context: dict[str, Any] | None = None,
    portfolio_summary: PortfolioSummary | None = None,
    output_root: Path | None = None,
) -> dict[str, Any]:
    root = output_root or Path("output")
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    datastore = get_datastore(output_root=root)
    period_changes = datastore.load_period_changes(run_date)
    refreshed_at = datetime.now().isoformat(timespec="seconds")

    index_path = data_dir / "index.json"
    if index_path.exists():
        payload = _load_json(index_path, default={})
        if isinstance(payload, dict):
            if market_overview is not None:
                payload["market_overview"] = market_overview
            if macro_context is not None:
                payload["macro_context"] = macro_context
            if portfolio_summary is not None:
                payload["portfolio_summary"] = _serialize_portfolio_summary(portfolio_summary)
            payload["date"] = run_date.isoformat()
            payload["intraday_refreshed_at"] = refreshed_at
            tickers = payload.get("tickers", [])
            if isinstance(tickers, list):
                payload["tickers"] = [
                    _patch_ticker_payload(ticker_payload, collected, period_changes)
                    for ticker_payload in tickers
                ]
            index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    tickers_dir = data_dir / "tickers"
    if tickers_dir.is_dir():
        for ticker_dir in tickers_dir.iterdir():
            if not ticker_dir.is_dir():
                continue
            latest_path = ticker_dir / "latest.json"
            if latest_path.exists():
                latest_payload = _load_json(latest_path, default={})
                if isinstance(latest_payload, dict) and isinstance(latest_payload.get("payload"), dict):
                    latest_payload["date"] = run_date.isoformat()
                    latest_payload["intraday_refreshed_at"] = refreshed_at
                    latest_payload["payload"] = _patch_ticker_payload(latest_payload["payload"], collected, period_changes)
                    latest_path.write_text(json.dumps(latest_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            history_path = ticker_dir / "history.json"
            if history_path.exists():
                history_payload = _load_json(history_path, default={})
                if isinstance(history_payload, dict) and isinstance(history_payload.get("days"), list):
                    days = []
                    for day_payload in history_payload["days"]:
                        if isinstance(day_payload, dict) and str(day_payload.get("date", "")) == run_date.isoformat():
                            days.append(_patch_ticker_payload(day_payload, collected, period_changes))
                        else:
                            days.append(day_payload)
                    history_payload["days"] = days
                    history_payload["intraday_refreshed_at"] = refreshed_at
                    history_path.write_text(json.dumps(history_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    price_rows = datastore.query_prices()
    price_history_json = data_dir / "price_history.json"
    price_history_json.write_text(json.dumps(price_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    dashboard_json = data_dir / "dashboard.json"
    _sync_intraday_outputs(
        root.parent,
        [
            index_path,
            price_history_json,
            dashboard_json,
        ],
        tickers_dir,
    )
    return {
        "date": run_date.isoformat(),
        "intraday_refreshed_at": refreshed_at,
        "tickers_refreshed": len(collected),
    }


def _patch_ticker_payload(
    payload: dict[str, Any],
    collected: dict[str, CollectedTickerData],
    period_changes: dict[str, dict[str, str]],
) -> dict[str, Any]:
    ticker = str(payload.get("ticker", "")).strip().upper()
    collected_data = collected.get(ticker)
    if not ticker or collected_data is None:
        return payload

    updated = dict(payload)
    updated["date"] = payload.get("date")
    updated["data_snapshot"] = _patch_data_snapshot(dict(payload.get("data_snapshot", {})), collected_data)
    updated["fundamentals"] = _patch_fundamentals(dict(payload.get("fundamentals", {})), collected_data)
    updated["price_action"] = _patch_price_action(dict(payload.get("price_action", {})), collected_data)
    updated["period_changes"] = {
        "7d": period_changes.get(ticker, {}).get("7d", payload.get("period_changes", {}).get("7d", "N/A")),
        "30d": period_changes.get(ticker, {}).get("30d", payload.get("period_changes", {}).get("30d", "N/A")),
    }
    if payload.get("options_summary"):
        updated["options_summary"] = {
            **dict(payload.get("options_summary", {})),
            **{key: value for key, value in collected_data.options_summary.items() if value not in ("", "N/A", None)},
        }
    return updated


def _patch_data_snapshot(snapshot: dict[str, str], collected: CollectedTickerData) -> dict[str, str]:
    price_text = f"{collected.price:,.2f} {collected.currency}" if collected.price is not None else snapshot.get("Price", "N/A")
    updated = {
        **snapshot,
        "Price": price_text,
        "Daily Change": _format_signed_percent(collected.change_percent) or snapshot.get("Daily Change", "N/A"),
        "Market Cap": collected.market_cap or snapshot.get("Market Cap", "N/A"),
        "Trailing P/E": collected.pe_ratio or snapshot.get("Trailing P/E", "N/A"),
        "EPS": collected.eps or snapshot.get("EPS", "N/A"),
        "52W High": collected.week52_high or snapshot.get("52W High", "N/A"),
        "52W Low": collected.week52_low or snapshot.get("52W Low", "N/A"),
        "50D SMA": collected.sma_50 or snapshot.get("50D SMA", "N/A"),
        "200D SMA": collected.sma_200 or snapshot.get("200D SMA", "N/A"),
        "Volume": collected.day_volume or snapshot.get("Volume", "N/A"),
        "3M Avg Volume": collected.avg_volume_3m or snapshot.get("3M Avg Volume", "N/A"),
        "Price/Book": collected.price_to_book or snapshot.get("Price/Book", "N/A"),
        "Dividend Yield": collected.dividend_yield or snapshot.get("Dividend Yield", "N/A"),
        "Open": collected.open_price or snapshot.get("Open", "N/A"),
        "High": collected.high_price or snapshot.get("High", "N/A"),
        "Low": collected.low_price or snapshot.get("Low", "N/A"),
        "Close": collected.close_price or snapshot.get("Close", "N/A"),
        "Sector": collected.sector or snapshot.get("Sector", "N/A"),
    }
    return updated


def _patch_fundamentals(fundamentals: dict[str, str], collected: CollectedTickerData) -> dict[str, str]:
    return {
        **fundamentals,
        "market_cap": collected.market_cap or fundamentals.get("market_cap", "N/A"),
        "trailing_pe": collected.pe_ratio or fundamentals.get("trailing_pe", "N/A"),
        "eps": collected.eps or fundamentals.get("eps", "N/A"),
        "forward_eps": collected.forward_eps or fundamentals.get("forward_eps", "N/A"),
        "earnings_growth": collected.earnings_growth or fundamentals.get("earnings_growth", "N/A"),
        "price_to_book": collected.price_to_book or fundamentals.get("price_to_book", "N/A"),
        "dividend_yield": collected.dividend_yield or fundamentals.get("dividend_yield", "N/A"),
        "volume": collected.day_volume or fundamentals.get("volume", "N/A"),
        "avg_volume_3m": collected.avg_volume_3m or fundamentals.get("avg_volume_3m", "N/A"),
        "52w_high": collected.week52_high or fundamentals.get("52w_high", "N/A"),
        "52w_low": collected.week52_low or fundamentals.get("52w_low", "N/A"),
        "analyst_target_price": collected.analyst_target_price or fundamentals.get("analyst_target_price", "N/A"),
        "analyst_recommendation": collected.analyst_recommendation or fundamentals.get("analyst_recommendation", "N/A"),
        "analyst_count": collected.analyst_count or fundamentals.get("analyst_count", "N/A"),
        "held_by_insiders": collected.held_by_insiders or fundamentals.get("held_by_insiders", "N/A"),
        "held_by_institutions": collected.held_by_institutions or fundamentals.get("held_by_institutions", "N/A"),
        "implied_volatility": collected.implied_volatility or fundamentals.get("implied_volatility", "N/A"),
        "short_float_pct": collected.short_float_pct or fundamentals.get("short_float_pct", "N/A"),
        "short_ratio": collected.short_ratio or fundamentals.get("short_ratio", "N/A"),
    }


def _patch_price_action(price_action: dict[str, str], collected: CollectedTickerData) -> dict[str, str]:
    return {
        **price_action,
        "atr_14d": collected.atr_14d or price_action.get("atr_14d", "N/A"),
        "atr_percent": collected.atr_percent or price_action.get("atr_percent", "N/A"),
        "relative_volume": collected.relative_volume or price_action.get("relative_volume", "N/A"),
        "gap_percent": collected.gap_percent or price_action.get("gap_percent", "N/A"),
        "price_vs_sma50": collected.price_vs_sma50 or price_action.get("price_vs_sma50", "N/A"),
        "price_vs_sma200": collected.price_vs_sma200 or price_action.get("price_vs_sma200", "N/A"),
        "week52_position": collected.week52_position or price_action.get("week52_position", "N/A"),
        "rs_vs_spy": collected.rs_vs_spy or price_action.get("rs_vs_spy", "N/A"),
        "rs_vs_sector_etf": collected.rs_vs_sector_etf or price_action.get("rs_vs_sector_etf", "N/A"),
    }


def _serialize_portfolio_summary(portfolio_summary: PortfolioSummary | None) -> dict[str, Any] | None:
    if portfolio_summary is None:
        return None
    return {
        "positions": [
            {
                "ticker": position.ticker,
                "shares": position.shares,
                "avg_cost": position.avg_cost,
                "currency": position.currency,
                "market_price": position.market_price,
                "market_value": position.market_value,
                "cost_basis": position.cost_basis,
                "unrealized_pnl": position.unrealized_pnl,
                "unrealized_return_pct": position.unrealized_return_pct,
            }
            for position in portfolio_summary.positions
        ],
        "total_market_value": portfolio_summary.total_market_value,
        "total_cost_basis": portfolio_summary.total_cost_basis,
        "total_unrealized_pnl": portfolio_summary.total_unrealized_pnl,
        "total_unrealized_return_pct": portfolio_summary.total_unrealized_return_pct,
    }


def _load_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _sync_intraday_outputs(project_root: Path, file_paths: list[Path], tickers_dir: Path) -> None:
    web_root = project_root / "web"
    if not web_root.exists():
        return
    target_dirs = [web_root / "public" / "output" / "data"]
    dist_root = web_root / "dist" / "output" / "data"
    if dist_root.parent.parent.exists():
        target_dirs.append(dist_root)

    for target_dir in target_dirs:
        target_dir.mkdir(parents=True, exist_ok=True)
        for file_path in file_paths:
            if file_path.exists():
                shutil.copy2(file_path, target_dir / file_path.name)
        if tickers_dir.is_dir():
            target_tickers = target_dir / "tickers"
            if target_tickers.exists():
                shutil.rmtree(target_tickers, ignore_errors=True)
            shutil.copytree(tickers_dir, target_tickers)


def _format_signed_percent(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value:+.2f}%"
