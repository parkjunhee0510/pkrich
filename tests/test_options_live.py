from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from src.api.options_live import (
    InvalidOptionContract,
    build_subscribe_message,
    build_contract_lookup_payload,
    get_polygon_api_key,
    normalize_option_aggregate,
    normalize_contract_row,
    normalize_provider_status,
    rank_contracts_for_underlying,
    run_options_relay,
    validate_option_contract,
)


def test_validate_option_contract_accepts_polygon_symbol() -> None:
    assert validate_option_contract("O:AAPL260116C00200000") == "O:AAPL260116C00200000"


@pytest.mark.parametrize("value", ["AAPL", "A.AAPL", "A.*", "O:*", "O:AAPL260116X00200000", "O:AAPL"])
def test_validate_option_contract_rejects_non_contract_symbols(value: str) -> None:
    with pytest.raises(InvalidOptionContract):
        validate_option_contract(value)


def test_get_polygon_api_key_loads_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("POLYGON_API_KEY=from-dotenv\n", encoding="utf-8")

    assert get_polygon_api_key() == "from-dotenv"


def test_normalize_option_aggregate_maps_second_bar() -> None:
    payload = {
        "ev": "A",
        "sym": "O:AAPL260116C00200000",
        "v": 42,
        "av": 1204,
        "op": 3.0,
        "vw": 3.11,
        "o": 3.1,
        "c": 3.12,
        "h": 3.15,
        "l": 3.05,
        "s": 1780617600000,
        "e": 1780617600999,
    }

    result = normalize_option_aggregate(payload)

    assert result == {
        "type": "aggregate",
        "source": "polygon_options",
        "recency": "delayed_15m",
        "channel": "A",
        "contract": "O:AAPL260116C00200000",
        "timestamp": 1780617600999,
        "open": 3.1,
        "high": 3.15,
        "low": 3.05,
        "close": 3.12,
        "volume": 42,
        "accumulated_volume": 1204,
        "vwap": 3.11,
    }


def test_normalize_option_aggregate_rejects_incomplete_message() -> None:
    assert normalize_option_aggregate({"ev": "A", "sym": "O:AAPL260116C00200000"}) is None


def test_normalize_provider_status_maps_auth_success() -> None:
    assert normalize_provider_status({"ev": "status", "status": "auth_success", "message": "authenticated"}) == {
        "type": "status",
        "status": "connected",
        "recency": "delayed_15m",
        "message": "authenticated",
    }


def test_normalize_provider_status_maps_auth_failed() -> None:
    assert normalize_provider_status({"ev": "status", "status": "auth_failed", "message": "bad key"}) == {
        "type": "status",
        "status": "provider_auth_failed",
        "recency": "delayed_15m",
        "message": "bad key",
    }


def test_normalize_contract_row_keeps_display_fields() -> None:
    row = {
        "ticker": "O:AAPL260116C00200000",
        "underlying_ticker": "AAPL",
        "contract_type": "call",
        "expiration_date": "2026-01-16",
        "strike_price": 200,
    }

    assert normalize_contract_row(row) == {
        "contract": "O:AAPL260116C00200000",
        "underlying_ticker": "AAPL",
        "type": "call",
        "expiration_date": "2026-01-16",
        "strike_price": 200.0,
        "label": "CALL 200 - 2026-01-16",
    }


def test_build_contract_lookup_payload_reports_missing_key() -> None:
    with patch("src.api.options_live.get_polygon_api_key", return_value=None):
        payload = build_contract_lookup_payload("aapl")

    assert payload["status"] == "missing_credentials"
    assert payload["ticker"] == "AAPL"
    assert payload["contracts"] == []


def test_build_contract_lookup_payload_uses_fetcher() -> None:
    raw = {
        "results": [
            {
                "ticker": "O:AAPL260116C00200000",
                "underlying_ticker": "AAPL",
                "contract_type": "call",
                "expiration_date": "2026-01-16",
                "strike_price": 200,
            }
        ]
    }

    with patch("src.api.options_live.get_polygon_api_key", return_value="key"):
        payload = build_contract_lookup_payload("aapl", fetcher=lambda _ticker, _limit, _api_key: raw)

    assert payload["status"] == "ok"
    assert payload["recency"] == "delayed_15m"
    assert payload["contracts"][0]["contract"] == "O:AAPL260116C00200000"


def test_build_contract_lookup_payload_ranks_contracts_near_underlying_price() -> None:
    raw = {
        "results": [
            {
                "ticker": "O:AAPL260116C00100000",
                "underlying_ticker": "AAPL",
                "contract_type": "call",
                "expiration_date": "2026-01-16",
                "strike_price": 100,
            },
            {
                "ticker": "O:AAPL260116C00200000",
                "underlying_ticker": "AAPL",
                "contract_type": "call",
                "expiration_date": "2026-01-16",
                "strike_price": 200,
            },
            {
                "ticker": "O:AAPL260116C00190000",
                "underlying_ticker": "AAPL",
                "contract_type": "call",
                "expiration_date": "2026-01-16",
                "strike_price": 190,
            },
        ]
    }
    seen: dict[str, int] = {}

    def fetcher(_ticker: str, limit: int, _api_key: str) -> dict[str, object]:
        seen["limit"] = limit
        return raw

    with patch("src.api.options_live.get_polygon_api_key", return_value="key"):
        payload = build_contract_lookup_payload("aapl", limit=2, underlying_price=195, fetcher=fetcher)

    assert seen["limit"] == 50
    assert [row["strike_price"] for row in payload["contracts"]] == [190.0, 200.0]


def test_rank_contracts_for_underlying_keeps_provider_order_without_price() -> None:
    contracts = [{"contract": "low", "strike_price": 100.0}, {"contract": "high", "strike_price": 200.0}]

    assert rank_contracts_for_underlying(contracts, None) == contracts


class FakeProviderSocket:
    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        self.sent: list[str] = []

    async def __aenter__(self) -> "FakeProviderSocket":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def send(self, payload: str) -> None:
        self.sent.append(payload)

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for message in self.messages:
            yield message


def test_build_subscribe_message_uses_second_aggregate_channel() -> None:
    assert json.loads(build_subscribe_message("O:AAPL260116C00200000")) == {
        "action": "subscribe",
        "params": "A.O:AAPL260116C00200000",
    }


def test_run_options_relay_reports_invalid_contract_without_connecting() -> None:
    sent_to_client: list[dict[str, object]] = []

    async def send_json(payload: dict[str, object]) -> None:
        sent_to_client.append(payload)

    def connect_factory(_url: str) -> FakeProviderSocket:
        raise AssertionError("provider socket should not open for invalid contracts")

    async def run() -> None:
        await run_options_relay("AAPL", send_json, api_key="key", connect_factory=connect_factory)

    asyncio.run(run())

    assert sent_to_client == [
        {
            "type": "status",
            "status": "invalid_contract",
            "recency": "delayed_15m",
            "message": "The option contract symbol is invalid",
        }
    ]


def test_run_options_relay_authenticates_subscribes_and_forwards_aggregates() -> None:
    provider = FakeProviderSocket(
        [
            json.dumps([{"ev": "status", "status": "auth_success", "message": "authenticated"}]),
            json.dumps(
                [
                    {
                        "ev": "A",
                        "sym": "O:AAPL260116C00200000",
                        "v": 1,
                        "av": 2,
                        "vw": 3.1,
                        "o": 3.0,
                        "h": 3.2,
                        "l": 2.9,
                        "c": 3.15,
                        "s": 1780617600000,
                        "e": 1780617600999,
                    }
                ]
            ),
        ]
    )
    sent_to_client: list[dict[str, object]] = []

    async def send_json(payload: dict[str, object]) -> None:
        sent_to_client.append(payload)

    async def run() -> None:
        await run_options_relay(
            "O:AAPL260116C00200000",
            send_json,
            api_key="key",
            connect_factory=lambda _url: provider,
        )

    asyncio.run(run())

    assert json.loads(provider.sent[0]) == {"action": "auth", "params": "key"}
    assert json.loads(provider.sent[1]) == {"action": "subscribe", "params": "A.O:AAPL260116C00200000"}
    assert sent_to_client[0]["status"] == "connected"
    assert sent_to_client[1]["type"] == "aggregate"
    assert sent_to_client[1]["close"] == 3.15
