"""Portfolio-level risk analytics shared by analyzer, decision, and output."""
from __future__ import annotations

import math
import re
from statistics import mean
from typing import Any

from src.types import CollectedTickerData, PortfolioRiskMetrics, PortfolioSummary

_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")
_MIN_CORRELATION_DAYS = 20
_MDD_WINDOW_DAYS = 20
_VAR_WINDOW_DAYS = 30


def build_portfolio_risk_report(
    portfolio_summary: PortfolioSummary | None,
    collected_data: dict[str, CollectedTickerData],
) -> dict[str, Any]:
    """Generate a portfolio risk report for output and decision usage."""
    if portfolio_summary is None or not portfolio_summary.positions:
        return _empty_report()

    total_value = portfolio_summary.total_market_value
    if total_value is None or total_value <= 0:
        return _empty_report()

    positions_by_weight = _build_positions_by_weight(portfolio_summary, collected_data, total_value)
    sector_exposure = _build_sector_exposure(positions_by_weight)
    concentration_warning = _check_concentration(positions_by_weight)
    sector_alerts = _check_sector_concentration(sector_exposure)
    total_atr_risk = sum(float(position.get("atr_risk_usd", 0.0)) for position in positions_by_weight)
    max_drawdown_2atr = total_atr_risk * 2
    max_drawdown_pct = (max_drawdown_2atr / total_value * 100) if total_value > 0 else None

    metrics = calculate_portfolio_risk_metrics(
        portfolio_summary,
        collected_data,
        positions_by_weight=positions_by_weight,
        sector_exposure=sector_exposure,
    )
    correlation_pairs = _build_correlation_warnings(metrics.correlation_matrix)
    position_sizing = _build_position_sizing(positions_by_weight, collected_data, total_value)
    drawdown_series = _build_portfolio_drawdown_series(portfolio_summary, collected_data)

    return {
        "positions_by_weight": positions_by_weight,
        "sector_exposure": sector_exposure,
        "concentration_warning": concentration_warning,
        "sector_concentration_alerts": sector_alerts,
        "correlation_pairs": correlation_pairs,
        "position_sizing": position_sizing,
        "total_atr_risk_usd": round(total_atr_risk, 2),
        "max_drawdown_2atr_usd": round(max_drawdown_2atr, 2),
        "max_drawdown_2atr_pct": _format_pct(max_drawdown_pct),
        "total_market_value": round(total_value, 2),
        "hhi": round(metrics.hhi, 1),
        "portfolio_beta": _round_or_none(metrics.portfolio_beta, 2),
        "correlation_matrix": metrics.correlation_matrix,
        "mdd_20d": _round_or_none(metrics.mdd_20d, 2),
        "mdd_20d_series": drawdown_series,
        "var_95": _round_or_none(metrics.var_95, 2),
        "risk_grade": metrics.risk_grade,
        "recommendations": metrics.recommendations,
    }


def calculate_portfolio_risk_metrics(
    portfolio_summary: PortfolioSummary,
    collected_data: dict[str, CollectedTickerData],
    *,
    positions_by_weight: list[dict[str, Any]] | None = None,
    sector_exposure: dict[str, float] | None = None,
) -> PortfolioRiskMetrics:
    total_value = portfolio_summary.total_market_value or 0.0
    if total_value <= 0:
        return PortfolioRiskMetrics(hhi=0.0, portfolio_beta=None)

    weights = positions_by_weight or _build_positions_by_weight(portfolio_summary, collected_data, total_value)
    sector_weights = sector_exposure or _build_sector_exposure(weights)
    hhi = sum(weight * weight for weight in sector_weights.values())
    portfolio_beta = _calculate_portfolio_beta(weights, collected_data)
    correlation_matrix = _compute_correlation_matrix(portfolio_summary, collected_data)
    drawdown_series = _build_portfolio_drawdown_series(portfolio_summary, collected_data)
    mdd_20d = _calculate_max_drawdown(drawdown_series)
    var_95 = _calculate_var_95(portfolio_summary, collected_data)
    risk_grade = _assign_risk_grade(hhi, portfolio_beta, correlation_matrix, mdd_20d, var_95)
    recommendations = _build_recommendations(
        hhi=hhi,
        sector_exposure=sector_weights,
        correlation_matrix=correlation_matrix,
        portfolio_beta=portfolio_beta,
        mdd_20d=mdd_20d,
        var_95=var_95,
    )

    return PortfolioRiskMetrics(
        hhi=hhi,
        portfolio_beta=portfolio_beta,
        correlation_matrix=correlation_matrix,
        mdd_20d=mdd_20d,
        var_95=var_95,
        risk_grade=risk_grade,
        recommendations=recommendations,
    )


def _build_positions_by_weight(
    portfolio_summary: PortfolioSummary,
    collected_data: dict[str, CollectedTickerData],
    total_value: float,
) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    for position in portfolio_summary.positions:
        if position.market_value is None:
            continue
        ticker = position.ticker
        collected = collected_data.get(ticker)
        sector = collected.sector if collected and collected.sector else "Unknown"
        weight_pct = (position.market_value / total_value) * 100
        atr_val = _parse_float(collected.atr_14d) if collected else None
        atr_risk = position.shares * atr_val if atr_val is not None else 0.0
        positions.append(
            {
                "ticker": ticker,
                "weight_pct": round(weight_pct, 1),
                "sector": sector,
                "market_value": round(position.market_value, 2),
                "atr_risk_usd": round(atr_risk, 2),
            }
        )
    positions.sort(key=lambda item: float(item["weight_pct"]), reverse=True)
    return positions


def _build_sector_exposure(positions_by_weight: list[dict[str, Any]]) -> dict[str, float]:
    sector_exposure: dict[str, float] = {}
    for position in positions_by_weight:
        sector = str(position.get("sector") or "Unknown")
        sector_exposure[sector] = sector_exposure.get(sector, 0.0) + float(position.get("weight_pct", 0.0))
    return {sector: round(weight, 1) for sector, weight in sorted(sector_exposure.items(), key=lambda item: -item[1])}


def _calculate_portfolio_beta(
    positions_by_weight: list[dict[str, Any]],
    collected_data: dict[str, CollectedTickerData],
) -> float | None:
    weighted_betas: list[float] = []
    total_weight = 0.0
    for position in positions_by_weight:
        ticker = str(position.get("ticker", ""))
        beta = _extract_beta(collected_data.get(ticker))
        if beta is None:
            continue
        weight_fraction = float(position.get("weight_pct", 0.0)) / 100.0
        weighted_betas.append(beta * weight_fraction)
        total_weight += weight_fraction
    if not weighted_betas or total_weight <= 0:
        return None
    return sum(weighted_betas) / total_weight


def _compute_correlation_matrix(
    portfolio_summary: PortfolioSummary,
    collected_data: dict[str, CollectedTickerData],
) -> dict[str, dict[str, float | None]]:
    tickers = [position.ticker for position in portfolio_summary.positions if position.ticker in collected_data]
    series_by_ticker = {ticker: _daily_returns(collected_data[ticker], window=_VAR_WINDOW_DAYS) for ticker in tickers}
    matrix: dict[str, dict[str, float | None]] = {}
    for left in tickers:
        row: dict[str, float | None] = {}
        for right in tickers:
            if left == right:
                row[right] = 1.0
                continue
            left_series = series_by_ticker.get(left, {})
            right_series = series_by_ticker.get(right, {})
            common_dates = sorted(set(left_series) & set(right_series))
            if len(common_dates) < _MIN_CORRELATION_DAYS:
                row[right] = None
                continue
            left_values = [left_series[d] for d in common_dates]
            right_values = [right_series[d] for d in common_dates]
            row[right] = _pearson(left_values, right_values)
        matrix[left] = row
    return matrix


def _build_portfolio_drawdown_series(
    portfolio_summary: PortfolioSummary,
    collected_data: dict[str, CollectedTickerData],
) -> list[dict[str, float | str]]:
    value_series = _build_portfolio_value_series(portfolio_summary, collected_data)
    if len(value_series) < 2:
        return []

    rolling_max = 0.0
    drawdowns: list[dict[str, float | str]] = []
    for point in value_series[-_MDD_WINDOW_DAYS:]:
        value = float(point["value"])
        rolling_max = max(rolling_max, value)
        drawdown_pct = ((value / rolling_max) - 1) * 100 if rolling_max > 0 else 0.0
        drawdowns.append({"date": point["date"], "drawdown_pct": round(drawdown_pct, 2)})
    return drawdowns


def _build_portfolio_value_series(
    portfolio_summary: PortfolioSummary,
    collected_data: dict[str, CollectedTickerData],
) -> list[dict[str, float | str]]:
    price_maps: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()

    for position in portfolio_summary.positions:
        collected = collected_data.get(position.ticker)
        if not collected:
            continue
        price_map = _price_map(collected)
        if len(price_map) < 2:
            continue
        price_maps[position.ticker] = price_map
        all_dates.update(price_map)

    if not price_maps or not all_dates:
        return []

    series: list[dict[str, float | str]] = []
    for date_key in sorted(all_dates):
        total_value = 0.0
        included = 0
        for position in portfolio_summary.positions:
            price = price_maps.get(position.ticker, {}).get(date_key)
            if price is None:
                continue
            total_value += price * position.shares
            included += 1
        if included == 0:
            continue
        series.append({"date": date_key, "value": round(total_value, 2)})
    return series


def _calculate_max_drawdown(drawdown_series: list[dict[str, float | str]]) -> float | None:
    values = [
        abs(float(point["drawdown_pct"]))
        for point in drawdown_series
        if isinstance(point, dict) and point.get("drawdown_pct") is not None
    ]
    if not values:
        return None
    return max(values)


def _calculate_var_95(
    portfolio_summary: PortfolioSummary,
    collected_data: dict[str, CollectedTickerData],
) -> float | None:
    value_series = _build_portfolio_value_series(portfolio_summary, collected_data)
    if len(value_series) < 2:
        return None
    recent_series = value_series[-_VAR_WINDOW_DAYS:]
    returns: list[float] = []
    previous_value: float | None = None
    for point in recent_series:
        value = float(point["value"])
        if previous_value and previous_value > 0:
            returns.append((value / previous_value) - 1)
        previous_value = value
    if len(returns) < 5:
        return None
    sorted_returns = sorted(returns)
    index = max(0, int(math.floor((len(sorted_returns) - 1) * 0.05)))
    percentile_return = sorted_returns[index]
    return abs(percentile_return) * 100


def _build_correlation_warnings(
    correlation_matrix: dict[str, dict[str, float | None]]
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for left, row in correlation_matrix.items():
        for right, corr in row.items():
            if left == right or corr is None:
                continue
            pair = tuple(sorted((left, right)))
            if pair in seen:
                continue
            seen.add(pair)
            if abs(corr) < 0.7:
                continue
            warnings.append(
                {
                    "ticker_1": pair[0],
                    "ticker_2": pair[1],
                    "correlation": f"{corr:.2f}",
                    "warning": f"{pair[0]}/{pair[1]} 상관계수 {corr:.2f}로 동행성이 높아 분산 효과가 제한됩니다.",
                }
            )
    warnings.sort(key=lambda item: abs(float(item["correlation"])), reverse=True)
    return warnings


def _build_position_sizing(
    positions_by_weight: list[dict[str, Any]],
    collected_data: dict[str, CollectedTickerData],
    total_value: float,
) -> list[dict[str, str]]:
    sizing_recs: list[dict[str, str]] = []
    account_size_for_sizing = total_value if total_value > 0 else 10000
    for position in positions_by_weight:
        ticker = str(position.get("ticker", ""))
        atr = _parse_float(collected_data.get(ticker).atr_14d) if ticker in collected_data else None
        if atr is None or atr <= 0:
            continue
        sizing_recs.append(compute_position_sizing(ticker, atr, account_size=account_size_for_sizing))
    return sizing_recs


def compute_position_sizing(
    ticker: str,
    atr: float,
    account_size: float = 10000,
    risk_percent: float = 1.0,
) -> dict[str, str]:
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


def _assign_risk_grade(
    hhi: float,
    portfolio_beta: float | None,
    correlation_matrix: dict[str, dict[str, float | None]],
    mdd_20d: float | None,
    var_95: float | None,
) -> str:
    score = 0
    if hhi >= 2500:
        score += 3
    elif hhi >= 1800:
        score += 2
    elif hhi >= 1000:
        score += 1

    if portfolio_beta is not None:
        if portfolio_beta >= 1.4:
            score += 2
        elif portfolio_beta >= 1.1:
            score += 1

    avg_corr = _average_absolute_correlation(correlation_matrix)
    if avg_corr is not None:
        if avg_corr >= 0.75:
            score += 2
        elif avg_corr >= 0.55:
            score += 1

    if mdd_20d is not None:
        if mdd_20d >= 12:
            score += 2
        elif mdd_20d >= 7:
            score += 1

    if var_95 is not None:
        if var_95 >= 3.5:
            score += 2
        elif var_95 >= 2.0:
            score += 1

    if score <= 1:
        return "A"
    if score <= 4:
        return "B"
    if score <= 7:
        return "C"
    return "D"


def _build_recommendations(
    *,
    hhi: float,
    sector_exposure: dict[str, float],
    correlation_matrix: dict[str, dict[str, float | None]],
    portfolio_beta: float | None,
    mdd_20d: float | None,
    var_95: float | None,
) -> list[str]:
    recommendations: list[str] = []
    if hhi >= 2500:
        top_sector = next(iter(sector_exposure.items()), ("특정 섹터", 0.0))
        recommendations.append(f"{top_sector[0]} 비중이 {top_sector[1]:.1f}%로 높아 일부 차익 실현 또는 보완 섹터 편입을 검토하세요.")
    elif hhi >= 1800:
        recommendations.append("상위 섹터 편중이 커지고 있어 신규 매수는 비중이 낮은 섹터를 우선 검토하는 편이 좋습니다.")

    avg_corr = _average_absolute_correlation(correlation_matrix)
    if avg_corr is not None and avg_corr >= 0.7:
        recommendations.append("보유 종목 간 상관성이 높아 분산 효과가 약합니다. 같은 움직임의 종목 일부를 줄이는 것이 유효합니다.")

    if portfolio_beta is not None and portfolio_beta >= 1.3:
        recommendations.append("포트폴리오 베타가 높아 시장 조정에 민감합니다. 저베타 종목 또는 현금 비중 보완을 고려하세요.")

    if mdd_20d is not None and mdd_20d >= 10:
        recommendations.append("최근 20거래일 최대 낙폭이 커졌습니다. 손절 기준과 포지션 크기를 다시 점검하는 것이 좋습니다.")

    if var_95 is not None and var_95 >= 3.0:
        recommendations.append("1일 VaR이 높아 단기 변동성이 큽니다. 레버리지와 고변동 종목 비중을 낮추는 편이 안전합니다.")

    if not recommendations:
        recommendations.append("현재 포트폴리오는 과도한 집중 신호가 크지 않습니다. 신규 비중 확대 시에도 분산 구조를 유지하세요.")
    return recommendations[:4]


def _average_absolute_correlation(correlation_matrix: dict[str, dict[str, float | None]]) -> float | None:
    values: list[float] = []
    seen: set[tuple[str, str]] = set()
    for left, row in correlation_matrix.items():
        for right, corr in row.items():
            if left == right or corr is None:
                continue
            pair = tuple(sorted((left, right)))
            if pair in seen:
                continue
            seen.add(pair)
            values.append(abs(corr))
    if not values:
        return None
    return mean(values)


def _check_concentration(positions: list[dict[str, Any]]) -> str:
    if not positions:
        return ""
    top_weight = float(positions[0]["weight_pct"]) if positions else 0.0
    top3_weight = sum(float(position["weight_pct"]) for position in positions[:3])
    warnings: list[str] = []
    if top_weight > 25:
        warnings.append(f"{positions[0]['ticker']}가 포트폴리오의 {top_weight:.0f}%를 차지해 단일 종목 집중도가 높습니다.")
    if len(positions) >= 3 and top3_weight > 60:
        top3_tickers = "/".join(str(position["ticker"]) for position in positions[:3])
        warnings.append(f"상위 3종목({top3_tickers})이 {top3_weight:.0f}%를 차지해 분산 효과가 약합니다.")
    return " | ".join(warnings) if warnings else ""


def _check_sector_concentration(sector_exposure: dict[str, float]) -> list[str]:
    alerts: list[str] = []
    for sector, weight in sector_exposure.items():
        if weight > 40:
            alerts.append(f"{sector} 섹터 비중 {weight:.0f}%로 40%를 넘는 집중 위험이 있습니다.")
    return alerts


def _empty_report() -> dict[str, Any]:
    return {
        "positions_by_weight": [],
        "sector_exposure": {},
        "concentration_warning": "",
        "sector_concentration_alerts": [],
        "correlation_pairs": [],
        "correlation_matrix": {},
        "position_sizing": [],
        "total_atr_risk_usd": 0,
        "max_drawdown_2atr_usd": 0,
        "max_drawdown_2atr_pct": "N/A",
        "total_market_value": 0,
        "hhi": 0.0,
        "portfolio_beta": None,
        "mdd_20d": None,
        "mdd_20d_series": [],
        "var_95": None,
        "risk_grade": "B",
        "recommendations": [],
    }


def _extract_beta(collected: CollectedTickerData | None) -> float | None:
    if collected is None:
        return None
    metrics = collected.fundamental_metrics if isinstance(collected.fundamental_metrics, dict) else {}
    beta = _parse_float(metrics.get("beta")) if metrics else None
    return beta


def _price_map(collected: CollectedTickerData) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in collected.historical_prices:
        if not isinstance(row, dict):
            continue
        date_key = str(row.get("date", "")).strip()
        price = _parse_float(row.get("close")) or _parse_float(row.get("price")) or _parse_float(row.get("Close"))
        if not date_key or price is None:
            continue
        result[date_key] = price
    return result


def _daily_returns(collected: CollectedTickerData, *, window: int) -> dict[str, float]:
    prices = _price_map(collected)
    if len(prices) < 2:
        return {}
    ordered = sorted(prices.items())
    returns: dict[str, float] = {}
    previous_price: float | None = None
    for date_key, price in ordered:
        if previous_price is not None and previous_price > 0:
            returns[date_key] = (price / previous_price) - 1
        previous_price = price
    if len(returns) <= window:
        return returns
    recent_dates = sorted(returns)[-window:]
    return {date_key: returns[date_key] for date_key in recent_dates}


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = mean(left)
    right_mean = mean(right)
    left_var = sum((value - left_mean) ** 2 for value in left)
    right_var = sum((value - right_mean) ** 2 for value in right)
    if left_var <= 0 or right_var <= 0:
        return None
    covariance = sum((l - left_mean) * (r - right_mean) for l, r in zip(left, right, strict=False))
    return covariance / math.sqrt(left_var * right_var)


def _parse_float(text: str | None | object) -> float | None:
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


def _round_or_none(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _format_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}%"
