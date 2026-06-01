"""Financial Modeling Prep (FMP) API collector.

Provides analyst estimate revisions, insider trading, institutional
holder changes, and earnings surprises data.

Uses the current ``/stable`` endpoints where available. Some datasets
still depend on plan-gated endpoints and will gracefully return empty
results when the active subscription does not include them.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from typing import Any
from urllib import request
from urllib.error import HTTPError

from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

_FMP_BASE = "https://financialmodelingprep.com"
_FMP_DELAY_SECONDS = 0.5
_FMP_LAST_CALL_AT: float = 0.0
_PLAN_LIMITED_ENDPOINTS: set[str] = set()
_PLAN_LIMITED_PATTERNS = (
    "stable/insider-trading/search",
    "stable/institutional-ownership/symbol-positions-summary",
    "stable/key-metrics",
    "stable/financial-ratios",
    "stable/historical-dividend",
    "stable/profile",
)


class FmpPlanLimitedError(RuntimeError):
    """Raised when the active FMP plan does not include an endpoint."""

    def __init__(self, endpoint: str) -> None:
        super().__init__(endpoint)
        self.endpoint = endpoint


class FmpRateLimitedError(RuntimeError):
    """Raised when the active FMP key is temporarily rate-limited."""

    def __init__(self, endpoint: str) -> None:
        super().__init__(endpoint)
        self.endpoint = endpoint


def _get_api_key() -> str | None:
    return os.getenv("FMP_API_KEY") or None


def _throttle() -> None:
    global _FMP_LAST_CALL_AT  # noqa: PLW0603
    now = time.monotonic()
    elapsed = now - _FMP_LAST_CALL_AT
    if elapsed < _FMP_DELAY_SECONDS:
        time.sleep(_FMP_DELAY_SECONDS - elapsed)
    _FMP_LAST_CALL_AT = time.monotonic()


def _fetch_json(endpoint: str, params: dict[str, str] | None = None) -> Any:
    api_key = _get_api_key()
    if not api_key:
        return None
    normalized_endpoint = endpoint.lstrip("/")
    if normalized_endpoint in _PLAN_LIMITED_ENDPOINTS:
        return None
    query_parts = [f"apikey={api_key}"]
    if params:
        query_parts.extend(f"{k}={v}" for k, v in params.items())
    url = f"{_FMP_BASE}/{normalized_endpoint}?{'&'.join(query_parts)}"
    _throttle()
    req = request.Request(url, headers={"Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise FmpPlanLimitedError(normalized_endpoint) from exc
        if exc.code == 429:
            raise FmpRateLimitedError(normalized_endpoint) from exc
        if exc.code == 402:
            if any(normalized_endpoint.startswith(pattern) for pattern in _PLAN_LIMITED_PATTERNS):
                if normalized_endpoint not in _PLAN_LIMITED_ENDPOINTS:
                    _PLAN_LIMITED_ENDPOINTS.add(normalized_endpoint)
                    record_pipeline_event(
                        "collector",
                        "info",
                        "fmp_plan_limited_endpoint",
                        endpoint=normalized_endpoint,
                    )
                return None
            raise FmpPlanLimitedError(normalized_endpoint) from exc
        raise


def is_fmp_ready() -> bool:
    """Check if FMP API key is set and host is reachable."""
    if not _get_api_key():
        return False
    return can_open_tcp_connection("financialmodelingprep.com", 443)


def should_collect_fmp_extended() -> bool:
    """Whether to call lower-priority, higher-volume FMP endpoints."""
    return is_env_flag_enabled("ENABLE_FMP_EXTENDED_FETCH", default=False)


# ── Analyst Estimate Revisions ──────────────────────────────────────

def collect_fmp_analyst_estimates(ticker: str, run_date: date) -> dict[str, str]:
    """Fetch analyst estimates and compute revision trends.

    Returns dict with keys: current_eps, 30d_ago_eps, 90d_ago_eps,
    current_revenue, revision_pct, direction.
    """
    try:
        data = _fetch_json("stable/analyst-estimates", {"symbol": ticker, "period": "annual", "page": "0", "limit": "8"})
        if not data or not isinstance(data, list):
            return {}

        # FMP returns estimates sorted newest first (annual/quarterly)
        estimates = [e for e in data if isinstance(e, dict)]
        if not estimates:
            return {}

        current = estimates[0]
        result: dict[str, str] = {}

        current_eps = _safe_float(current.get("estimatedEpsAvg") or current.get("epsAvg"))
        if current_eps is not None:
            result["current_eps"] = f"{current_eps:.2f}"

        current_rev = _safe_float(current.get("estimatedRevenueAvg") or current.get("revenueAvg"))
        if current_rev is not None:
            result["current_revenue"] = _format_large(current_rev)

        # Find estimates from ~30 and ~90 days ago for revision comparison
        for entry in estimates[1:]:
            entry_date = entry.get("date", "")
            if not entry_date:
                continue
            try:
                ed = date.fromisoformat(entry_date)
            except (ValueError, TypeError):
                continue
            days_diff = (run_date - ed).days
            eps_val = _safe_float(entry.get("estimatedEpsAvg") or entry.get("epsAvg"))
            if eps_val is None:
                continue

            if 20 <= days_diff <= 45 and "30d_ago_eps" not in result:
                result["30d_ago_eps"] = f"{eps_val:.2f}"
            elif 75 <= days_diff <= 120 and "90d_ago_eps" not in result:
                result["90d_ago_eps"] = f"{eps_val:.2f}"

        # Compute revision direction
        if current_eps is not None:
            compare_eps = _safe_float(result.get("30d_ago_eps")) or _safe_float(result.get("90d_ago_eps"))
            if compare_eps is not None and compare_eps != 0:
                pct = ((current_eps - compare_eps) / abs(compare_eps)) * 100
                result["revision_pct"] = f"{pct:+.1f}%"
                if pct > 1:
                    result["direction"] = "up"
                elif pct < -1:
                    result["direction"] = "down"
                else:
                    result["direction"] = "stable"

        if result:
            record_pipeline_event(
                "collector", "info", "fmp_analyst_estimates",
                ticker=ticker, fields=len(result),
            )
        return result
    except FmpPlanLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_analyst_estimates_unavailable",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return {}
    except FmpRateLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_analyst_estimates_throttled",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return {}
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "fmp_analyst_estimates_failed",
            ticker=ticker, error=str(exc),
        )
        return {}


# ── Insider Trading ─────────────────────────────────────────────────

def collect_fmp_insider_trading(ticker: str, run_date: date) -> list[dict[str, str]]:
    """Fetch recent insider transactions (last 90 days)."""
    try:
        data = _fetch_json("stable/insider-trading/search", {"symbol": ticker, "page": "0", "limit": "20"})
        if not data or not isinstance(data, list):
            return []

        cutoff = run_date - timedelta(days=90)
        results: list[dict[str, str]] = []

        for tx in data:
            if not isinstance(tx, dict):
                continue
            tx_date_str = str(tx.get("transactionDate") or tx.get("filingDate") or "")
            try:
                tx_date = date.fromisoformat(tx_date_str)
            except (ValueError, TypeError):
                continue
            if tx_date < cutoff:
                continue

            shares = _safe_float(tx.get("securitiesTransacted") or tx.get("securitiesOwned"))
            price = _safe_float(tx.get("price"))
            value = shares * price if shares and price else None

            results.append({
                "name": str(tx.get("reportingName") or tx.get("reportingCikName") or "Unknown"),
                "title": str(tx.get("typeOfOwner") or tx.get("reportingName") or ""),
                "type": _classify_transaction(
                    str(tx.get("acquistionOrDisposition") or tx.get("acquisitionOrDisposition") or ""),
                    str(tx.get("transactionType") or tx.get("typeOfTransaction") or ""),
                ),
                "shares": f"{int(shares):,}" if shares else "N/A",
                "value": _format_money(value),
                "date": tx_date_str,
            })

        if results:
            record_pipeline_event(
                "collector", "info", "fmp_insider_trading",
                ticker=ticker, count=len(results),
            )
        return results[:10]
    except FmpPlanLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_insider_trading_unavailable",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return []
    except FmpRateLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_insider_trading_throttled",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return []
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "fmp_insider_trading_failed",
            ticker=ticker, error=str(exc),
        )
        return []


# ── Institutional Holders ───────────────────────────────────────────

def collect_fmp_institutional_holders(ticker: str) -> dict[str, str]:
    """Fetch top institutional holders and compute net flow."""
    try:
        data = _fetch_json("stable/institutional-ownership/symbol-positions-summary", {
            "symbol": ticker,
            "year": str(_latest_completed_year()),
            "quarter": str(_latest_completed_quarter()),
        })
        if not data or not isinstance(data, list):
            return {}

        holders = [h for h in data if isinstance(h, dict)][:10]
        if not holders:
            return {}

        total_shares = sum(_safe_float(h.get("shares")) or 0 for h in holders)
        total_change = sum(_safe_float(h.get("change")) or 0 for h in holders)

        # Find biggest buyer and seller
        buyers = sorted(
            [h for h in holders if (_safe_float(h.get("change")) or 0) > 0],
            key=lambda h: _safe_float(h.get("change")) or 0,
            reverse=True,
        )
        sellers = sorted(
            [h for h in holders if (_safe_float(h.get("change")) or 0) < 0],
            key=lambda h: _safe_float(h.get("change")) or 0,
        )

        result: dict[str, str] = {
            "total_institutional_shares": _format_large(total_shares),
            "net_change": _format_shares_change(total_change),
        }

        if buyers:
            b = buyers[0]
            change = _safe_float(b.get("change")) or 0
            result["top_buyer"] = f"{b.get('holder', 'Unknown')} {_format_shares_change(change)}"

        if sellers:
            s = sellers[0]
            change = _safe_float(s.get("change")) or 0
            result["top_seller"] = f"{s.get('holder', 'Unknown')} {_format_shares_change(change)}"

        if result:
            record_pipeline_event(
                "collector", "info", "fmp_institutional_holders",
                ticker=ticker, holders=len(holders),
            )
        return result
    except FmpPlanLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_institutional_holders_unavailable",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return {}
    except FmpRateLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_institutional_holders_throttled",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return {}
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "fmp_institutional_holders_failed",
            ticker=ticker, error=str(exc),
        )
        return {}


# ── Earnings Surprises ──────────────────────────────────────────────

def collect_fmp_earnings_surprises(ticker: str) -> list[dict[str, str]]:
    """Fetch historical earnings surprises (actual vs estimated)."""
    try:
        data = _fetch_json("stable/earnings", {"symbol": ticker})
        if not data or not isinstance(data, list):
            return []

        results: list[dict[str, str]] = []
        for entry in data[:8]:
            if not isinstance(entry, dict):
                continue
            actual = _safe_float(entry.get("actualEarningResult") or entry.get("epsActual"))
            estimated = _safe_float(entry.get("estimatedEarning") or entry.get("epsEstimated"))

            row: dict[str, str] = {
                "date": str(entry.get("date", "")),
            }
            if actual is not None:
                row["actual"] = f"{actual:.2f}"
            if estimated is not None:
                row["estimated"] = f"{estimated:.2f}"
            if actual is not None and estimated is not None and estimated != 0:
                surprise = ((actual - estimated) / abs(estimated)) * 100
                row["surprise_pct"] = f"{surprise:+.1f}%"
                row["beat_miss"] = "beat" if surprise > 0 else ("miss" if surprise < 0 else "in-line")

            results.append(row)

        if results:
            record_pipeline_event(
                "collector", "info", "fmp_earnings_surprises",
                ticker=ticker, count=len(results),
            )
        return results
    except FmpPlanLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_earnings_surprises_unavailable",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return []
    except FmpRateLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_earnings_surprises_throttled",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return []
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "fmp_earnings_surprises_failed",
            ticker=ticker, error=str(exc),
        )
        return []


# ── FMP News ────────────────────────────────────────────────────────

def collect_fmp_news(ticker: str, limit: int = 5) -> list[dict[str, str]]:
    """Fetch company-specific news from FMP (included in Starter plan)."""
    try:
        data = _fetch_json("api/v3/stock_news", {"tickers": ticker, "limit": str(limit)})
        if not data or not isinstance(data, list):
            return []

        results: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            results.append({
                "title": str(item.get("title", "")),
                "source": str(item.get("site", "")),
                "published_at": str(item.get("publishedDate", "")),
                "link": str(item.get("url", "")),
                "sentiment": str(item.get("sentiment", "")),
            })
        return results
    except Exception:
        return []


# ── Key Metrics & Financial Ratios ─────────────────────────────────

def collect_fmp_key_metrics(ticker: str) -> dict[str, str]:
    """Fetch key financial metrics (ROE, ROIC, D/E, FCF yield, etc.)."""
    try:
        data = _fetch_json("stable/key-metrics", {"symbol": ticker, "period": "annual", "limit": "3"})
        if not data or not isinstance(data, list):
            return {}

        latest = data[0] if isinstance(data[0], dict) else {}
        if not latest:
            return {}

        result: dict[str, str] = {}

        roe = _safe_float(latest.get("roe") or latest.get("returnOnEquity"))
        if roe is not None:
            result["roe"] = f"{roe * 100:.1f}%" if abs(roe) < 10 else f"{roe:.1f}%"

        roic = _safe_float(latest.get("roic") or latest.get("returnOnCapitalEmployed"))
        if roic is not None:
            result["roic"] = f"{roic * 100:.1f}%" if abs(roic) < 10 else f"{roic:.1f}%"

        current_ratio = _safe_float(latest.get("currentRatio"))
        if current_ratio is not None:
            result["current_ratio"] = f"{current_ratio:.2f}"

        de = _safe_float(latest.get("debtToEquity"))
        if de is not None:
            result["debt_to_equity"] = f"{de:.2f}"

        fcf_yield = _safe_float(latest.get("freeCashFlowYield"))
        if fcf_yield is not None:
            result["fcf_yield"] = f"{fcf_yield * 100:.1f}%" if abs(fcf_yield) < 10 else f"{fcf_yield:.1f}%"

        net_debt_ebitda = _safe_float(latest.get("netDebtToEBITDA"))
        if net_debt_ebitda is not None:
            result["net_debt_to_ebitda"] = f"{net_debt_ebitda:.1f}x"

        if result:
            record_pipeline_event(
                "collector", "info", "fmp_key_metrics",
                ticker=ticker, fields=len(result),
            )
        return result
    except FmpPlanLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_key_metrics_unavailable",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return {}
    except FmpRateLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_key_metrics_throttled",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return {}
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "fmp_key_metrics_failed",
            ticker=ticker, error=str(exc),
        )
        return {}


def collect_fmp_peer_metrics(tickers: list[str]) -> dict[str, dict[str, str]]:
    """Fetch simplified metrics for peer comparison (PE, ROE, margin, 30d change).

    Returns dict keyed by ticker with metrics for each peer.
    """
    result: dict[str, dict[str, str]] = {}
    for ticker in tickers:
        try:
            metrics = collect_fmp_key_metrics(ticker)
            ratios = collect_fmp_financial_ratios(ticker)
            profile = collect_fmp_company_profile(ticker)
            if metrics or ratios or profile:
                combined: dict[str, str] = {}
                for key in ('roe', 'gross_margin'):
                    val = metrics.get(key) or ratios.get(key)
                    if val:
                        combined[key] = val
                for key in ('market_cap', 'pe_ratio', 'avg_volume', 'sector'):
                    val = profile.get(key)
                    if val:
                        combined[key] = val
                result[ticker] = combined
        except Exception:
            continue
    return result


def collect_fmp_financial_ratios(ticker: str) -> dict[str, str]:
    """Fetch financial ratios with 3-year trend (gross/operating margin)."""
    try:
        data = _fetch_json("stable/financial-ratios", {"symbol": ticker, "period": "annual", "limit": "3"})
        if not data or not isinstance(data, list):
            return {}

        entries = [e for e in data if isinstance(e, dict)]
        if not entries:
            return {}

        latest = entries[0]
        result: dict[str, str] = {}

        gross_margin = _safe_float(latest.get("grossProfitMargin"))
        if gross_margin is not None:
            result["gross_margin"] = f"{gross_margin * 100:.1f}%" if abs(gross_margin) < 10 else f"{gross_margin:.1f}%"

        op_margin = _safe_float(latest.get("operatingProfitMargin"))
        if op_margin is not None:
            result["operating_margin"] = f"{op_margin * 100:.1f}%" if abs(op_margin) < 10 else f"{op_margin:.1f}%"

        # Compute 3-year trend for margins
        if len(entries) >= 2:
            oldest = entries[-1]
            gm_latest = _safe_float(latest.get("grossProfitMargin"))
            gm_oldest = _safe_float(oldest.get("grossProfitMargin"))
            if gm_latest is not None and gm_oldest is not None:
                diff = gm_latest - gm_oldest
                result["gross_margin_trend"] = "improving" if diff > 0.01 else ("declining" if diff < -0.01 else "stable")

            om_latest = _safe_float(latest.get("operatingProfitMargin"))
            om_oldest = _safe_float(oldest.get("operatingProfitMargin"))
            if om_latest is not None and om_oldest is not None:
                diff = om_latest - om_oldest
                result["operating_margin_trend"] = "improving" if diff > 0.01 else ("declining" if diff < -0.01 else "stable")

        if result:
            record_pipeline_event(
                "collector", "info", "fmp_financial_ratios",
                ticker=ticker, fields=len(result),
            )
        return result
    except FmpPlanLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_financial_ratios_unavailable",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return {}
    except FmpRateLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_financial_ratios_throttled",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return {}
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "fmp_financial_ratios_failed",
            ticker=ticker, error=str(exc),
        )
        return {}


def _dividend_5y_cagr(annual_divs: list[float]) -> str | None:
    """True 5-year dividend CAGR.

    ``annual_divs`` is ordered most-recent-year first. A genuine 5-year span
    needs 6 annual buckets (year 0 vs year -5), so we require >= 6 entries and
    use exponent 1/5. (The most-recent bucket can be a partial current year,
    which understates the rate slightly — an accepted simplification.)
    """
    if len(annual_divs) >= 6 and annual_divs[0] > 0 and annual_divs[5] > 0:
        cagr = (annual_divs[0] / annual_divs[5]) ** (1 / 5) - 1
        return f"{cagr * 100:.1f}%"
    return None


def collect_fmp_dividend_history(ticker: str) -> dict[str, str]:
    """Fetch dividend history: recent dividend, 5-year CAGR, consecutive increase years."""
    try:
        # limit 24 ~= 6 years of quarterly payments, enough for a true 5y CAGR.
        data = _fetch_json("stable/historical-dividend", {"symbol": ticker, "limit": "24"})
        if not data or not isinstance(data, list):
            return {}

        dividends = [e for e in data if isinstance(e, dict) and _safe_float(e.get("dividend")) is not None]
        if not dividends:
            return {}

        result: dict[str, str] = {}

        # Most recent dividend
        latest = dividends[0]
        latest_div = _safe_float(latest.get("dividend"))
        if latest_div is not None:
            result["latest_dividend"] = f"${latest_div:.4f}"
            result["latest_dividend_date"] = str(latest.get("date", "N/A"))

        # Annual dividend sum (last 4 quarters approximate)
        annual_divs: list[float] = []
        year_groups: dict[str, float] = {}
        for entry in dividends:
            d = _safe_float(entry.get("dividend"))
            date_str = str(entry.get("date", ""))
            year = date_str[:4] if len(date_str) >= 4 else ""
            if d is not None and year:
                year_groups[year] = year_groups.get(year, 0.0) + d

        sorted_years = sorted(year_groups.keys(), reverse=True)
        for y in sorted_years:
            annual_divs.append(year_groups[y])

        if annual_divs:
            result["annual_dividend"] = f"${annual_divs[0]:.2f}"

        # 5-year CAGR (true 5-year span; see _dividend_5y_cagr)
        cagr_str = _dividend_5y_cagr(annual_divs)
        if cagr_str is not None:
            result["dividend_5y_cagr"] = cagr_str

        # Consecutive increase years
        consecutive = 0
        for i in range(len(annual_divs) - 1):
            if annual_divs[i] > annual_divs[i + 1]:
                consecutive += 1
            else:
                break
        if consecutive > 0:
            result["consecutive_increase_years"] = str(consecutive)

        if result:
            record_pipeline_event(
                "collector", "info", "fmp_dividend_history",
                ticker=ticker, fields=len(result),
            )
        return result
    except FmpPlanLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_dividend_history_unavailable",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return {}
    except FmpRateLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_dividend_history_throttled",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return {}
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "fmp_dividend_history_failed",
            ticker=ticker, error=str(exc),
        )
        return {}


def collect_fmp_company_profile(ticker: str) -> dict[str, str]:
    """Fetch company profile: sector, industry, description, full-time employees."""
    try:
        data = _fetch_json("stable/profile", {"symbol": ticker})
        if not data:
            return {}

        entry = data[0] if isinstance(data, list) and data else data
        if not isinstance(entry, dict):
            return {}

        result: dict[str, str] = {}

        sector = entry.get("sector")
        if sector and str(sector).strip() and str(sector).strip() != "N/A":
            result["sector"] = str(sector).strip()

        industry = entry.get("industry")
        if industry and str(industry).strip() and str(industry).strip() != "N/A":
            result["industry"] = str(industry).strip()

        beta = _safe_float(entry.get("beta"))
        if beta is not None:
            result["beta"] = f"{beta:.2f}"

        market_cap = _safe_float(entry.get("marketCap") or entry.get("mktCap"))
        if market_cap is not None and market_cap > 0:
            result["market_cap"] = f"{market_cap:.0f}"

        pe_ratio = _safe_float(entry.get("pe") or entry.get("priceEarningsRatioTTM"))
        if pe_ratio is not None and pe_ratio > 0:
            result["pe_ratio"] = f"{pe_ratio:.2f}x"

        avg_volume = _safe_float(entry.get("volAvg") or entry.get("avgVolume"))
        if avg_volume is not None and avg_volume > 0:
            result["avg_volume"] = f"{avg_volume:.0f}"

        employees = entry.get("fullTimeEmployees")
        if employees:
            result["full_time_employees"] = str(employees)

        description = entry.get("description")
        if description and isinstance(description, str):
            # Truncate to first 200 chars for token efficiency
            result["description"] = description[:200].strip()

        div_yield = _safe_float(entry.get("lastDiv"))
        if div_yield is not None and div_yield > 0:
            result["last_annual_dividend"] = f"${div_yield:.2f}"

        if result:
            record_pipeline_event(
                "collector", "info", "fmp_company_profile",
                ticker=ticker, fields=len(result),
            )
        return result
    except FmpPlanLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_company_profile_unavailable",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return {}
    except FmpRateLimitedError as exc:
        record_pipeline_event(
            "collector", "info", "fmp_company_profile_throttled",
            ticker=ticker, endpoint=exc.endpoint,
        )
        return {}
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "fmp_company_profile_failed",
            ticker=ticker, error=str(exc),
        )
        return {}


# ── Helpers ─────────────────────────────────────────────────────────

def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
        if f != f:  # NaN check
            return None
        return f
    except (TypeError, ValueError):
        return None


def _format_large(value: float | None) -> str:
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"${value / 1e12:.1f}T"
    if abs_val >= 1e9:
        return f"${value / 1e9:.1f}B"
    if abs_val >= 1e6:
        return f"${value / 1e6:.1f}M"
    if abs_val >= 1e3:
        return f"${value / 1e3:.0f}K"
    return f"${value:.0f}"


def _format_money(value: float | None) -> str:
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1e6:
        return f"${value / 1e6:.1f}M"
    if abs_val >= 1e3:
        return f"${value / 1e3:.0f}K"
    return f"${value:,.0f}"


def _format_shares_change(value: float) -> str:
    if value >= 1e6:
        return f"+{value / 1e6:.1f}M shares"
    if value <= -1e6:
        return f"{value / 1e6:.1f}M shares"
    if value >= 1e3:
        return f"+{value / 1e3:.0f}K shares"
    if value <= -1e3:
        return f"{value / 1e3:.0f}K shares"
    return f"{value:+,.0f} shares"


def _classify_transaction(acq_disp: str, tx_type: str) -> str:
    acq_disp = (acq_disp or "").upper()
    tx_type = (tx_type or "").lower()
    if acq_disp == "A" or "purchase" in tx_type or "buy" in tx_type:
        return "buy"
    if acq_disp == "D" or "sale" in tx_type or "sell" in tx_type:
        return "sale"
    if "option" in tx_type or "exercise" in tx_type:
        return "option_exercise"
    return "other"


def _latest_completed_year() -> int:
    today = date.today()
    quarter = _latest_completed_quarter()
    if quarter == 4:
        return today.year - 1
    return today.year


def _latest_completed_quarter() -> int:
    month = date.today().month
    if month <= 3:
        return 4
    if month <= 6:
        return 1
    if month <= 9:
        return 2
    return 3
