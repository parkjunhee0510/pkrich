from __future__ import annotations

import json
import os
import re
from collections.abc import Awaitable, Callable
from typing import Any
from urllib import parse, request

from src.utils.env import load_dotenv

DELAYED_OPTIONS_WS_URL = "wss://delayed.massive.com/options"
POLYGON_REST_BASE = "https://api.polygon.io"
RECENCY = "delayed_15m"
SOURCE = "polygon_options"

_OPTION_CONTRACT_RE = re.compile(r"^O:[A-Z0-9]{1,8}\d{6}[CP]\d{8}$")


class InvalidOptionContract(ValueError):
    """Raised when a user-provided options symbol is not a single Polygon contract."""


def get_polygon_api_key() -> str | None:
    load_dotenv()
    return os.getenv("POLYGON_API_KEY") or os.getenv("MASSIVE_API_KEY") or None


def validate_option_contract(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if "*" in normalized or not _OPTION_CONTRACT_RE.match(normalized):
        raise InvalidOptionContract(f"Invalid option contract: {value}")
    return normalized


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_option_aggregate(message: dict[str, Any]) -> dict[str, Any] | None:
    if message.get("ev") != "A":
        return None
    try:
        contract = validate_option_contract(str(message.get("sym", "")))
    except InvalidOptionContract:
        return None

    open_price = _safe_float(message.get("o"))
    high = _safe_float(message.get("h"))
    low = _safe_float(message.get("l"))
    close = _safe_float(message.get("c"))
    timestamp = _safe_int(message.get("e")) or _safe_int(message.get("s"))
    if None in (open_price, high, low, close, timestamp):
        return None

    return {
        "type": "aggregate",
        "source": SOURCE,
        "recency": RECENCY,
        "channel": "A",
        "contract": contract,
        "timestamp": timestamp,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": _safe_int(message.get("v")) or 0,
        "accumulated_volume": _safe_int(message.get("av")) or 0,
        "vwap": _safe_float(message.get("vw")),
    }


def status_payload(status: str, message: str = "") -> dict[str, str]:
    return {
        "type": "status",
        "status": status,
        "recency": RECENCY,
        "message": message,
    }


def normalize_provider_status(message: dict[str, Any]) -> dict[str, str] | None:
    if message.get("ev") != "status":
        return None
    raw_status = str(message.get("status", "")).lower()
    text = str(message.get("message", ""))
    if raw_status == "auth_success":
        return status_payload("connected", text or "authenticated")
    if raw_status in {"auth_failed", "error"} and (raw_status == "auth_failed" or "auth" in text.lower()):
        return status_payload("provider_auth_failed", text)
    if raw_status in {"error", "max_connections", "not_authorized"}:
        return status_payload("provider_no_access", text)
    if raw_status in {"connected", "success"}:
        return status_payload("connecting", text)
    return status_payload(raw_status or "provider_disconnected", text)


def parse_provider_messages(raw: str) -> list[dict[str, Any]]:
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(decoded, list):
        return [item for item in decoded if isinstance(item, dict)]
    return [decoded] if isinstance(decoded, dict) else []


SendJson = Callable[[dict[str, Any]], Awaitable[None]]


def normalize_underlying_ticker(value: str) -> str:
    return "".join(ch for ch in str(value or "").upper().strip() if ch.isalnum() or ch in {".", "-"})


def normalize_contract_row(row: dict[str, Any]) -> dict[str, Any] | None:
    try:
        contract = validate_option_contract(str(row.get("ticker", "")))
    except InvalidOptionContract:
        return None
    contract_type = str(row.get("contract_type", "")).lower()
    if contract_type not in {"call", "put"}:
        return None
    strike = _safe_float(row.get("strike_price"))
    expiration = str(row.get("expiration_date", "")).strip()
    if strike is None or not expiration:
        return None
    label_side = "CALL" if contract_type == "call" else "PUT"
    return {
        "contract": contract,
        "underlying_ticker": normalize_underlying_ticker(str(row.get("underlying_ticker", ""))),
        "type": contract_type,
        "expiration_date": expiration,
        "strike_price": strike,
        "label": f"{label_side} {strike:g} - {expiration}",
    }


def rank_contracts_for_underlying(
    contracts: list[dict[str, Any]],
    underlying_price: float | None,
) -> list[dict[str, Any]]:
    price = _safe_float(underlying_price)
    if price is None or price <= 0:
        return contracts

    def sort_key(contract: dict[str, Any]) -> tuple[str, float, int, float, str]:
        strike = _safe_float(contract.get("strike_price")) or price
        contract_type_rank = 0 if contract.get("type") == "call" else 1
        return (
            str(contract.get("expiration_date", "")),
            abs(strike - price),
            contract_type_rank,
            strike,
            str(contract.get("contract", "")),
        )

    return sorted(contracts, key=sort_key)


def fetch_polygon_option_contracts(ticker: str, limit: int, api_key: str) -> dict[str, Any]:
    normalized = normalize_underlying_ticker(ticker)
    query = parse.urlencode(
        {
            "underlying_ticker": normalized,
            "expired": "false",
            "limit": str(max(1, min(limit, 50))),
            "sort": "expiration_date",
            "order": "asc",
            "apiKey": api_key,
        }
    )
    url = f"{POLYGON_REST_BASE}/v3/reference/options/contracts?{query}"
    req = request.Request(url, headers={"Accept": "application/json"})
    with request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def build_contract_lookup_payload(
    ticker: str,
    *,
    limit: int = 12,
    underlying_price: float | None = None,
    fetcher: Callable[[str, int, str], dict[str, Any]] = fetch_polygon_option_contracts,
) -> dict[str, Any]:
    normalized_ticker = normalize_underlying_ticker(ticker)
    api_key = get_polygon_api_key()
    if not api_key:
        return {
            "status": "missing_credentials",
            "ticker": normalized_ticker,
            "recency": RECENCY,
            "contracts": [],
            "message": "POLYGON_API_KEY or MASSIVE_API_KEY is not configured",
        }
    try:
        provider_limit = 50 if _safe_float(underlying_price) else limit
        raw = fetcher(normalized_ticker, provider_limit, api_key)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "provider_error",
            "ticker": normalized_ticker,
            "recency": RECENCY,
            "contracts": [],
            "message": str(exc),
        }

    rows = raw.get("results") if isinstance(raw, dict) else None
    contracts = [
        normalized
        for row in (rows if isinstance(rows, list) else [])
        if isinstance(row, dict)
        for normalized in [normalize_contract_row(row)]
        if normalized is not None
    ]
    ranked_contracts = rank_contracts_for_underlying(contracts, underlying_price)[:limit]
    return {
        "status": "ok" if ranked_contracts else "empty",
        "ticker": normalized_ticker,
        "recency": RECENCY,
        "contracts": ranked_contracts,
        "message": "",
    }


def build_auth_message(api_key: str) -> str:
    return json.dumps({"action": "auth", "params": api_key})


def build_subscribe_message(contract: str) -> str:
    return json.dumps({"action": "subscribe", "params": f"A.{validate_option_contract(contract)}"})


def default_connect_factory(url: str):
    import websockets

    return websockets.connect(url, ping_interval=20, ping_timeout=20)


async def run_options_relay(
    contract: str,
    send_json: SendJson,
    *,
    api_key: str | None = None,
    connect_factory: Callable[[str], Any] | None = None,
) -> None:
    try:
        normalized_contract = validate_option_contract(contract)
    except InvalidOptionContract:
        await send_json(status_payload("invalid_contract", "The option contract symbol is invalid"))
        return

    key = api_key or get_polygon_api_key()
    if not key:
        await send_json(status_payload("missing_credentials", "POLYGON_API_KEY or MASSIVE_API_KEY is not configured"))
        return

    factory = connect_factory or default_connect_factory
    try:
        async with factory(DELAYED_OPTIONS_WS_URL) as provider_socket:
            await provider_socket.send(build_auth_message(key))
            subscribed = False
            async for raw_message in provider_socket:
                for message in parse_provider_messages(str(raw_message)):
                    status = normalize_provider_status(message)
                    if status is not None:
                        await send_json(status)
                        if status["status"] == "connected" and not subscribed:
                            await provider_socket.send(build_subscribe_message(normalized_contract))
                            subscribed = True
                        continue
                    aggregate = normalize_option_aggregate(message)
                    if aggregate is not None and aggregate["contract"] == normalized_contract:
                        await send_json(aggregate)
    except Exception as exc:  # noqa: BLE001
        text = str(exc)
        status = "rate_limited" if "429" in text or "rate" in text.lower() else "provider_disconnected"
        await send_json(status_payload(status, text))
