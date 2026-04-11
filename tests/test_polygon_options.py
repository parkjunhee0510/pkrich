"""Unit tests for Polygon options Tier A metrics."""

from __future__ import annotations

from src.collector.polygon_options import (
    _compute_gex,
    _compute_greeks_aggregates,
    _compute_implied_move,
    _compute_iv_skew,
    _compute_max_pain,
    _compute_oi_concentration,
    _compute_oi_ratio,
    _compute_unusual_activity_v2,
    _extract_spot_price,
    _parse_contracts,
)


def _make_contract(
    ctype: str = "call",
    strike: float = 150.0,
    volume: float = 100,
    oi: float = 500,
    iv: float | None = 0.30,
    delta: float | None = 0.50,
    gamma: float | None = 0.02,
    theta: float | None = -0.05,
    vega: float | None = 0.10,
    dte: int | None = 14,
    mid_price: float | None = 3.50,
) -> dict:
    from datetime import date, timedelta

    expiry = date.today() + timedelta(days=dte) if dte is not None else None
    return {
        "type": ctype,
        "strike": strike,
        "volume": volume,
        "oi": oi,
        "iv": iv,
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "expiry": expiry,
        "dte": dte,
        "mid_price": mid_price,
    }


class TestMaxPain:
    def test_basic_three_strikes(self):
        contracts = [
            _make_contract("call", strike=100, oi=1000),
            _make_contract("call", strike=110, oi=500),
            _make_contract("call", strike=120, oi=200),
            _make_contract("put", strike=100, oi=200),
            _make_contract("put", strike=110, oi=800),
            _make_contract("put", strike=120, oi=1500),
        ]
        result = _compute_max_pain(contracts, spot=110.0)
        assert result is not None
        assert "max_pain" in result
        assert "$" in result["max_pain"]

    def test_includes_vs_spot(self):
        contracts = [
            _make_contract("call", strike=100, oi=1000),
            _make_contract("call", strike=110, oi=500),
            _make_contract("call", strike=120, oi=200),
            _make_contract("put", strike=100, oi=500),
            _make_contract("put", strike=110, oi=1000),
            _make_contract("put", strike=120, oi=300),
        ]
        result = _compute_max_pain(contracts, spot=105.0)
        assert result is not None
        assert "vs spot" in result["max_pain"]

    def test_no_spot_omits_percent(self):
        contracts = [
            _make_contract("call", strike=100, oi=1000),
            _make_contract("call", strike=110, oi=500),
            _make_contract("call", strike=120, oi=200),
            _make_contract("put", strike=100, oi=500),
            _make_contract("put", strike=110, oi=1000),
            _make_contract("put", strike=120, oi=300),
        ]
        result = _compute_max_pain(contracts, spot=None)
        assert result is not None
        assert "vs spot" not in result["max_pain"]

    def test_too_few_strikes(self):
        contracts = [
            _make_contract("call", strike=100, oi=1000),
            _make_contract("put", strike=100, oi=1000),
        ]
        result = _compute_max_pain(contracts, spot=100.0)
        assert result is None


class TestImpliedMove:
    def test_basic_calculation(self):
        contracts = [
            _make_contract("call", strike=100, iv=0.30, dte=14),
            _make_contract("put", strike=100, iv=0.40, dte=14),
        ]
        result = _compute_implied_move(contracts, spot=100.0)
        assert result is not None
        assert "implied_move" in result
        assert "%" in result["implied_move"]
        assert "14d" in result["implied_move"]

    def test_no_spot_returns_none(self):
        contracts = [_make_contract("call", iv=0.30, dte=14)]
        assert _compute_implied_move(contracts, spot=None) is None

    def test_zero_dte_excluded(self):
        contracts = [_make_contract("call", iv=0.30, dte=0)]
        assert _compute_implied_move(contracts, spot=100.0) is None


class TestGex:
    def test_basic_gex(self):
        contracts = [
            _make_contract("call", strike=100, gamma=0.02, oi=1000),
            _make_contract("put", strike=100, gamma=0.02, oi=1000),
        ]
        result = _compute_gex(contracts, spot=100.0)
        assert result is not None
        assert "gex_regime" in result
        # Call contributes positive, put contributes negative
        # With equal gamma/oi, they cancel → flat or near-zero

    def test_no_gamma_returns_none(self):
        contracts = [_make_contract("call", gamma=None)]
        assert _compute_gex(contracts, spot=100.0) is None

    def test_no_spot_returns_none(self):
        contracts = [_make_contract("call", gamma=0.02, oi=1000)]
        assert _compute_gex(contracts, spot=None) is None


class TestGreeksAggregates:
    def test_basic_aggregation(self):
        contracts = [
            _make_contract("call", delta=0.50, gamma=0.02, oi=1000),
            _make_contract("put", delta=-0.30, gamma=0.01, oi=500),
        ]
        result = _compute_greeks_aggregates(contracts)
        assert "net_delta" in result
        assert "total_gamma" in result

    def test_no_greeks_returns_empty(self):
        contracts = [_make_contract("call", delta=None, gamma=None)]
        assert _compute_greeks_aggregates(contracts) == {}


class TestIvSkew:
    def test_basic_skew(self):
        contracts = [
            _make_contract("put", strike=90, delta=-0.25, iv=0.35, dte=14),
            _make_contract("call", strike=110, delta=0.25, iv=0.28, dte=14),
        ]
        result = _compute_iv_skew(contracts, spot=100.0)
        assert result is not None
        assert "iv_skew" in result
        # Put IV (0.35) > Call IV (0.28) → positive skew → fear-biased
        assert "fear-biased" in result["iv_skew"]

    def test_delta_too_far_returns_none(self):
        contracts = [
            _make_contract("put", strike=90, delta=-0.05, iv=0.35, dte=14),
            _make_contract("call", strike=110, delta=0.05, iv=0.28, dte=14),
        ]
        # delta deviation from 0.25 is 0.20 > max_deviation 0.15
        assert _compute_iv_skew(contracts, spot=100.0) is None


class TestOiConcentration:
    def test_top_3(self):
        contracts = [
            _make_contract("call", strike=100, oi=5000),
            _make_contract("call", strike=110, oi=8000),
            _make_contract("call", strike=120, oi=3000),
            _make_contract("call", strike=130, oi=12000),
            _make_contract("put", strike=95, oi=7000),
            _make_contract("put", strike=90, oi=10000),
        ]
        result = _compute_oi_concentration(contracts)
        assert "top_call_oi" in result
        assert "top_put_oi" in result
        # Top call by OI: 130 (12K), 110 (8K), 100 (5K)
        assert "$130" in result["top_call_oi"]


class TestOiRatio:
    def test_basic(self):
        contracts = [
            _make_contract("call", oi=1000),
            _make_contract("put", oi=800),
        ]
        result = _compute_oi_ratio(contracts)
        assert result["put_call_oi_ratio"] == "0.80"

    def test_zero_calls(self):
        contracts = [_make_contract("put", oi=800)]
        # No call OI → empty
        assert _compute_oi_ratio(contracts) == {}


class TestUnusualActivityV2:
    def test_premium_sorting(self):
        contracts = [
            _make_contract("call", strike=100, volume=600, oi=100, mid_price=2.0),  # prem=120K
            _make_contract("put", strike=90, volume=3000, oi=100, mid_price=0.50),  # prem=150K
        ]
        result = _compute_unusual_activity_v2(contracts)
        assert len(result) == 2
        # PUT $90 has higher premium → should be first
        assert result[0]["side"] == "PUT"
        assert result[0]["premium_usd"] == 150000

    def test_no_unusual(self):
        contracts = [_make_contract("call", volume=100, oi=500)]  # vol/oi = 0.2 < 5
        assert _compute_unusual_activity_v2(contracts) == []


class TestParseContracts:
    def test_parse_polygon_format(self):
        raw = [
            {
                "details": {"contract_type": "call", "strike_price": 150, "expiration_date": "2026-05-01"},
                "day": {"volume": 200, "close": 3.5, "vwap": 3.4},
                "open_interest": 1000,
                "implied_volatility": 0.28,
                "greeks": {"delta": 0.55, "gamma": 0.03, "theta": -0.04, "vega": 0.12},
            },
        ]
        result = _parse_contracts(raw)
        assert len(result) == 1
        c = result[0]
        assert c["type"] == "call"
        assert c["strike"] == 150
        assert c["volume"] == 200
        assert c["oi"] == 1000
        assert c["iv"] == 0.28
        assert c["delta"] == 0.55
        assert c["mid_price"] == 3.5

    def test_missing_greeks_graceful(self):
        raw = [
            {
                "details": {"contract_type": "put", "strike_price": 140, "expiration_date": "2026-05-01"},
                "day": {"volume": 50},
                "open_interest": 300,
                "implied_volatility": 0.32,
            },
        ]
        result = _parse_contracts(raw)
        assert len(result) == 1
        assert result[0]["delta"] is None
        assert result[0]["gamma"] is None

    def test_invalid_strike_filtered(self):
        raw = [
            {"details": {"contract_type": "call", "strike_price": 0}, "day": {}, "open_interest": 100},
            {"details": {"contract_type": "call"}, "day": {}, "open_interest": 100},
        ]
        assert _parse_contracts(raw) == []


class TestExtractSpotPrice:
    def test_basic(self):
        data = {"results": [{"underlying_asset": {"price": 148.72}}]}
        assert _extract_spot_price(data) == 148.72

    def test_missing(self):
        assert _extract_spot_price({}) is None
        assert _extract_spot_price({"results": []}) is None
