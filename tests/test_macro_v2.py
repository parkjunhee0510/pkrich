"""Tests for Macro 2.0 additions: surprise index, forward-signal regime scoring, and sector-regime factor."""
from __future__ import annotations

from datetime import date

import pytest

from src.collector.macro_surprise import collect_macro_surprise
from src.decision.factors.macro_regime_factor import MacroRegimeFactor
from src.decision.market_regime import detect_market_regime
from src.types import MarketRegime, TickerAnalysis


def _macro_base() -> dict:
    return {
        "vix": {"level": "14", "change": "-1%", "regime": "낮은 변동성"},
        "spy_technicals": {"close": "500", "sma50": "490", "sma200": "470"},
        "us10y": {"level": "4.2", "change": "0.0%"},
        "us2y": {"level": "4.0"},
        "copper": {"change": "+1%"},
        "dxy": {"change": "-0.2%"},
    }


class TestSurpriseIndex:
    def test_empty_inputs_return_low_confidence(self) -> None:
        result = collect_macro_surprise(date.today(), upcoming_events=[])
        assert result["confidence"] == "low"
        assert result["composite"] == 0.0

    def test_cpi_hot_is_negative_on_inflation_axis(self) -> None:
        events = [
            {"category": "inflation", "event": "CPI", "actual": "3.5", "consensus": "3.0"},
            {"category": "inflation", "event": "CPI", "actual": "3.3", "consensus": "3.0"},
            {"category": "inflation", "event": "CPI", "actual": "3.4", "consensus": "3.0"},
        ]
        result = collect_macro_surprise(date.today(), upcoming_events=events)
        # Hot inflation = bad for risk → inflation axis score should be negative.
        assert result["inflation"]["score"] < 0

    def test_growth_beat_is_positive_on_growth_axis(self) -> None:
        events = [
            {"category": "consumer", "event": "Retail Sales", "actual": "1.2", "consensus": "0.6"},
            {"category": "manufacturing", "event": "ISM", "actual": "52", "consensus": "50"},
        ]
        result = collect_macro_surprise(date.today(), upcoming_events=events)
        assert result["growth"]["score"] > 0


class TestForwardSignalRegime:
    def test_reflation_detected_when_curve_steepens_with_growth_surprise(self) -> None:
        ctx = _macro_base()
        ctx["yield_curve_10y_2y"] = {"level": "+0.50", "spread_bps": "+50", "status": "normal"}
        ctx["surprise_score"] = {
            "composite": 0.6,
            "growth": {"score": 0.5, "samples": 3},
            "inflation": {"score": 0.0, "samples": 0},
            "labor": {"score": 0.0, "samples": 0},
            "confidence": "medium",
        }
        regime = detect_market_regime([], ctx, {}, date.today())
        assert regime.regime == "reflation"
        assert regime.sub_regime == "reflation"

    def test_defensive_bias_on_credit_widening(self) -> None:
        ctx = _macro_base()
        ctx["vix"] = {"level": "26", "change": "+5%", "regime": "경계"}
        ctx["spy_technicals"] = {"close": "430", "sma50": "450", "sma200": "470"}
        ctx["hyg"] = {"change": "-1.5%"}
        ctx["lqd"] = {"change": "-0.2%"}
        regime = detect_market_regime([], ctx, {}, date.today())
        assert regime.sub_regime == "defensive_bias"

    def test_inverted_curve_pushes_score_negative(self) -> None:
        ctx = {
            "vix": {"level": "22", "change": "+1%", "regime": "정상 범위"},
            "spy_technicals": {"close": "480", "sma50": "485", "sma200": "470"},
            "us10y": {"level": "4.2", "change": "+1.0%"},
            "yield_curve_10y_2y": {"level": "-0.20", "spread_bps": "-20", "status": "inverted"},
        }
        regime = detect_market_regime([], ctx, {}, date.today())
        # Inverted curve (-2) plus neutral/slightly-negative baseline should not land in risk_on.
        assert regime.regime != "risk_on"


class TestMacroRegimeFactor:
    @pytest.mark.parametrize(
        ("sector", "regime_name", "expect_positive"),
        [
            ("Technology", "risk_on", True),
            ("Technology", "risk_off", False),
            ("Consumer Defensive", "risk_off", True),
            ("Energy", "reflation", True),
            ("Utilities", "defensive_bias", True),
        ],
    )
    def test_sector_regime_tilt(self, sector: str, regime_name: str, expect_positive: bool) -> None:
        factor = MacroRegimeFactor()
        analysis = TickerAnalysis(
            ticker="X",
            name="Test",
            date="2026-04-22",
            summary="",
            key_news=[],
            news_references=[],
            financial_highlights=[],
            risks_or_watchpoints=[],
            signal_or_takeaway="",
            data_snapshot={"Sector": sector},
        )
        regime = MarketRegime(regime=regime_name)  # type: ignore[arg-type]
        score = factor.score(analysis, None, regime, {})
        if expect_positive:
            assert score.value > 0
        else:
            assert score.value < 0
