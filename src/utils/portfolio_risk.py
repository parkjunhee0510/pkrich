"""Portfolio-level risk analytics: exposure, concentration, sector allocation."""
from __future__ import annotations

import re
from typing import Any

from src.types import CollectedTickerData, PortfolioSummary

_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def build_portfolio_risk_report(
    portfolio_summary: PortfolioSummary | None,
    collected_data: dict[str, CollectedTickerData],
) -> dict[str, Any]:
    """Generate a portfolio risk report.

    Returns dict with:
    - positions_by_weight: list of {ticker, weight_pct, sector}
    - sector_exposure: dict of sector -> weight_pct
    - concentration_warning: text if top position > 25% or top 3 > 60%
    - max_drawdown_estimate: simple 2×ATR-based worst case
    - total_atr_risk: portfolio-weighted ATR risk in dollars
    """
    if portfolio_summary is None or not portfolio_summary.positions:
        return _empty_report()

    total_value = portfolio_summary.total_market_value
    if total_value is None or total_value <= 0:
        return _empty_report()

    positions_by_weight: list[dict[str, Any]] = []
    sector_exposure: dict[str, float] = {}
    total_atr_risk = 0.0

    for position in portfolio_summary.positions:
        if position.market_value is None:
            continue

        weight = (position.market_value / total_value) * 100
        ticker = position.ticker
        collected = collected_data.get(ticker)
        sector = collected.sector if collected else "Unknown"

        atr_val = _parse_float(collected.atr_14d) if collected else None
        position_atr_risk = position.shares * atr_val if atr_val is not None else 0.0

        positions_by_weight.append({
            "ticker": ticker,
            "weight_pct": round(weight, 1),
            "sector": sector,
            "market_value": round(position.market_value, 2),
            "atr_risk_usd": round(position_atr_risk, 2),
        })

        sector_exposure[sector] = sector_exposure.get(sector, 0.0) + weight
        total_atr_risk += position_atr_risk

    positions_by_weight.sort(key=lambda p: p["weight_pct"], reverse=True)

    # Concentration check
    concentration_warning = _check_concentration(positions_by_weight)

    # Simple max drawdown estimate: 2×ATR across portfolio
    max_drawdown_2atr = total_atr_risk * 2
    max_drawdown_pct = (max_drawdown_2atr / total_value * 100) if total_value > 0 else 0

    # Round sector exposure
    sector_exposure_rounded = {k: round(v, 1) for k, v in sorted(sector_exposure.items(), key=lambda x: -x[1])}

    # Sector concentration alerts
    sector_alerts = _check_sector_concentration(sector_exposure_rounded)

    # Correlation analysis from price history
    correlation_pairs = compute_correlation_warnings(collected_data)

    # Position sizing recommendations
    sizing_recs: list[dict[str, str]] = []
    account_size_for_sizing = total_value if total_value and total_value > 0 else 10000
    for pos in positions_by_weight:
        atr = _parse_float(collected_data.get(pos["ticker"], CollectedTickerData(
            ticker="", name="", sector="", price=None, change_percent=None,
            currency="USD", market_cap="N/A", pe_ratio="N/A", summary_note="",
        )).atr_14d) if pos["ticker"] in collected_data else None
        if atr and atr > 0:
            sizing = compute_position_sizing(pos["ticker"], atr, account_size=account_size_for_sizing)
            sizing_recs.append(sizing)

    return {
        "positions_by_weight": positions_by_weight,
        "sector_exposure": sector_exposure_rounded,
        "concentration_warning": concentration_warning,
        "sector_concentration_alerts": sector_alerts,
        "correlation_pairs": correlation_pairs,
        "position_sizing": sizing_recs,
        "total_atr_risk_usd": round(total_atr_risk, 2),
        "max_drawdown_2atr_usd": round(max_drawdown_2atr, 2),
        "max_drawdown_2atr_pct": f"{max_drawdown_pct:.1f}%",
        "total_market_value": round(total_value, 2),
    }


def _check_concentration(positions: list[dict[str, Any]]) -> str:
    if not positions:
        return ""

    top_weight = positions[0]["weight_pct"] if positions else 0
    top3_weight = sum(p["weight_pct"] for p in positions[:3])

    warnings: list[str] = []
    if top_weight > 25:
        warnings.append(f"{positions[0]['ticker']}이(가) 포트폴리오의 {top_weight:.0f}%를 차지 — 집중도 높음")
    if len(positions) >= 3 and top3_weight > 60:
        top3_tickers = "/".join(p["ticker"] for p in positions[:3])
        warnings.append(f"상위 3종목({top3_tickers})이 {top3_weight:.0f}% — 분산 부족")

    return " | ".join(warnings) if warnings else ""


def compute_correlation_warnings(
    collected_data: dict[str, CollectedTickerData],
) -> list[dict[str, str]]:
    """Compute pairwise return correlations and warn on high correlation (>0.7).

    Uses price_history.csv if available, otherwise returns empty.
    """
    import os
    csv_path = os.path.join("output", "data", "price_history.csv")
    if not os.path.exists(csv_path):
        return []
    try:
        import pandas as pd
    except ImportError:
        return []

    try:
        df = pd.read_csv(csv_path)
        if "date" not in df.columns:
            return []

        tickers = [t for t in collected_data if t in df.columns]
        if len(tickers) < 2:
            return []

        prices = df[["date"] + tickers].dropna()
        if len(prices) < 20:
            return []

        returns = prices[tickers].pct_change().dropna()
        corr_matrix = returns.corr()

        warnings: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for i, t1 in enumerate(tickers):
            for j, t2 in enumerate(tickers):
                if i >= j:
                    continue
                pair = (t1, t2)
                if pair in seen:
                    continue
                seen.add(pair)
                corr_val = corr_matrix.loc[t1, t2]
                if abs(corr_val) > 0.7:
                    warnings.append({
                        "ticker_1": t1,
                        "ticker_2": t2,
                        "correlation": f"{corr_val:.2f}",
                        "warning": f"{t1}/{t2} 상관계수 {corr_val:.2f} — 동조화 높음, 분산 효과 제한",
                    })
        return warnings
    except Exception:
        return []


def compute_position_sizing(
    ticker: str,
    atr: float,
    account_size: float = 10000,
    risk_percent: float = 1.0,
) -> dict[str, str]:
    """ATR-based position sizing (2×ATR stop distance)."""
    normalized_account_size = account_size if account_size and account_size > 0 else 10000
    max_risk_usd = normalized_account_size * risk_percent / 100
    stop_distance = atr * 2
    shares = int(max_risk_usd / stop_distance) if stop_distance > 0 else 0
    return {
        "ticker": ticker,
        "recommended_shares": str(shares),
        "max_risk_usd": f"${max_risk_usd:.0f}",
        "stop_distance": f"${stop_distance:.2f}",
        "account_size": f"${normalized_account_size:.0f}",
    }


def _check_sector_concentration(sector_exposure: dict[str, float]) -> list[str]:
    """Warn if any single sector exceeds 40%."""
    alerts: list[str] = []
    for sector, weight in sector_exposure.items():
        if weight > 40:
            alerts.append(f"{sector} 섹터 비중 {weight:.0f}% — 40% 초과 집중 위험")
    return alerts


def _empty_report() -> dict[str, Any]:
    return {
        "positions_by_weight": [],
        "sector_exposure": {},
        "concentration_warning": "",
        "sector_concentration_alerts": [],
        "correlation_pairs": [],
        "position_sizing": [],
        "total_atr_risk_usd": 0,
        "max_drawdown_2atr_usd": 0,
        "max_drawdown_2atr_pct": "N/A",
        "total_market_value": 0,
    }


def _parse_float(text: str | None) -> float | None:
    if text is None:
        return None
    cleaned = str(text).strip()
    if not cleaned or cleaned == "N/A":
        return None
    match = _NUMBER_PATTERN.search(cleaned.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None
