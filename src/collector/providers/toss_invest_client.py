from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import requests

_DEFAULT_BASE_URL = "https://openapi.tossinvest.com"
_TOKEN_SKEW_SECONDS = 60


class TossInvestApiError(RuntimeError):
    """Raised when Toss Invest returns an unusable API response."""


class TossInvestClient:
    """Small read-only Toss Invest Open API client.

    The client intentionally exposes only market-data and stock-info endpoints.
    Account and order endpoints stay outside this integration.
    """

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        session: Any | None = None,
        access_token: str | None = None,
        now: Callable[[], float] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.client_id = (client_id or os.getenv("TOSS_INVEST_CLIENT_ID") or "").strip()
        self.client_secret = (client_secret or os.getenv("TOSS_INVEST_CLIENT_SECRET") or "").strip()
        self.base_url = str(base_url or _DEFAULT_BASE_URL).rstrip("/")
        self.session = session or requests.Session()
        self._access_token = str(access_token or "").strip()
        self._token_expires_at = float("inf") if self._access_token else 0.0
        self._now = now or time.time
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def issue_token(self) -> str:
        if not self.is_configured:
            raise TossInvestApiError("Toss Invest credentials are missing")

        payload = self._request_json(
            "POST",
            "/oauth2/token",
            authorized=False,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise TossInvestApiError("Toss Invest token response did not include access_token")
        self._access_token = token
        self._token_expires_at = self._now() + _positive_int(payload.get("expires_in"), 0) - _TOKEN_SKEW_SECONDS
        return token

    def get_prices(self, symbols: list[str]) -> dict[str, Any]:
        return self._request_json(
            "GET",
            "/api/v1/prices",
            params={"symbols": _symbols_param(symbols)},
        )

    def get_candles(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        count: int = 100,
        before: str | None = None,
        adjusted: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "symbol": _normalize_symbol(symbol),
            "interval": interval,
            "count": max(1, min(int(count), 200)),
            "adjusted": bool(adjusted),
        }
        if before:
            params["before"] = before
        return self._request_json("GET", "/api/v1/candles", params=params)

    def get_stocks(self, symbols: list[str]) -> dict[str, Any]:
        return self._request_json(
            "GET",
            "/api/v1/stocks",
            params={"symbols": _symbols_param(symbols)},
        )

    def get_stock_warnings(self, symbol: str) -> dict[str, Any]:
        encoded_symbol = quote(_normalize_symbol(symbol), safe="")
        return self._request_json("GET", f"/api/v1/stocks/{encoded_symbol}/warnings")

    def get_exchange_rate(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        date_time: str | None = None,
    ) -> dict[str, Any]:
        params = {
            "baseCurrency": str(base_currency or "").strip().upper(),
            "quoteCurrency": str(quote_currency or "").strip().upper(),
        }
        if date_time:
            params["dateTime"] = date_time
        return self._request_json("GET", "/api/v1/exchange-rate", params=params)

    def get_market_calendar(self, country: str, *, target_date: str | None = None) -> dict[str, Any]:
        normalized_country = str(country or "").strip().upper()
        if normalized_country not in {"KR", "US"}:
            raise TossInvestApiError(f"Unsupported market calendar country: {country}")
        params = {"date": target_date} if target_date else None
        return self._request_json("GET", f"/api/v1/market-calendar/{normalized_country}", params=params)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        authorized: bool = True,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if authorized:
            headers["Authorization"] = f"Bearer {self._ensure_token()}"

        response = self.session.request(
            method.upper(),
            f"{self.base_url}{path}",
            params=params,
            data=data,
            headers=headers,
            timeout=self.timeout,
        )
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code >= 400:
            raise TossInvestApiError(f"Toss Invest API returned HTTP {status_code}: {getattr(response, 'text', '')}")

        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise TossInvestApiError(f"Toss Invest API returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise TossInvestApiError("Toss Invest API response must be a JSON object")
        return payload

    def _ensure_token(self) -> str:
        if self._access_token and self._now() < self._token_expires_at:
            return self._access_token
        return self.issue_token()


def _symbols_param(symbols: list[str]) -> str:
    normalized = [_normalize_symbol(symbol) for symbol in symbols if _normalize_symbol(symbol)]
    if not normalized:
        raise TossInvestApiError("At least one symbol is required")
    return ",".join(normalized[:200])


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


__all__ = ["TossInvestApiError", "TossInvestClient"]
