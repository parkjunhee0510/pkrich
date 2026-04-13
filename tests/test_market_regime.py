"""Tests for src.decision.market_regime — market regime detection."""
from __future__ import annotations

import unittest
from datetime import date

from src.decision.market_regime import detect_market_regime
from src.types import CollectedTickerData


_CTD_REQUIRED = {
    "ticker": "TEST",
    "name": "Test Corp",
    "sector": "Technology",
    "price": 100.0,
    "change_percent": 0.5,
    "currency": "USD",
    "market_cap": "1T",
    "pe_ratio": "25",
    "summary_note": "",
}


def _make_ctd(**overrides: object) -> CollectedTickerData:
    """Build a CollectedTickerData with required positional args filled."""
    kwargs = {**_CTD_REQUIRED, **overrides}
    return CollectedTickerData(**kwargs)  # type: ignore[arg-type]


class TestDetectMarketRegime(unittest.TestCase):

    def test_risk_on_low_vix_above_sma(self) -> None:
        """Low VIX + SPY above both SMAs + breadth positive → risk_on."""
        macro = {
            "vix": {"level": "12", "regime": "저변동성"},
            "spy_technicals": {"close": "500", "sma50": "490", "sma200": "470"},
            "us10y": {"level": "4.0", "change": "-0.5"},
        }
        # 3 tickers all above SMA50
        collected = {
            "AAPL": _make_ctd(price_vs_sma50="3.0"),
            "MSFT": _make_ctd(price_vs_sma50="5.0"),
            "GOOG": _make_ctd(price_vs_sma50="2.0"),
        }
        regime = detect_market_regime([], macro, collected, date(2026, 4, 10))
        self.assertEqual(regime.regime, "risk_on")
        self.assertGreater(regime.confidence, 0)
        self.assertIn("vix", regime.drivers)
        self.assertIn("trend", regime.drivers)

    def test_risk_off_high_vix_below_sma(self) -> None:
        """High VIX + SPY below both SMAs + breadth negative → risk_off."""
        macro = {
            "vix": {"level": "35", "regime": "고변동성"},
            "spy_technicals": {"close": "400", "sma50": "450", "sma200": "470"},
            "us10y": {"level": "5.0", "change": "5.0"},
        }
        collected = {
            "AAPL": _make_ctd(price_vs_sma50="-8.0"),
            "MSFT": _make_ctd(price_vs_sma50="-5.0"),
            "GOOG": _make_ctd(price_vs_sma50="-3.0"),
        }
        regime = detect_market_regime([], macro, collected, date(2026, 4, 10))
        self.assertEqual(regime.regime, "risk_off")
        self.assertGreater(regime.confidence, 0)

    def test_neutral_mixed_signals(self) -> None:
        """Mixed signals → neutral."""
        macro = {
            "vix": {"level": "22"},
            "spy_technicals": {"close": "460", "sma50": "455", "sma200": "470"},
            "us10y": {"level": "4.2", "change": "0.1"},
        }
        collected = {
            "AAPL": _make_ctd(price_vs_sma50="2.0"),
            "MSFT": _make_ctd(price_vs_sma50="-3.0"),
        }
        regime = detect_market_regime([], macro, collected, date(2026, 4, 10))
        self.assertEqual(regime.regime, "neutral")

    def test_empty_data_returns_neutral(self) -> None:
        """No macro data → neutral regime with zero confidence."""
        regime = detect_market_regime([], {}, {}, date(2026, 4, 10))
        self.assertEqual(regime.regime, "neutral")
        self.assertEqual(regime.confidence, 0)
        self.assertEqual(regime.assessed_at, "2026-04-10")

    def test_implication_text_populated(self) -> None:
        """Regime implication should always be a non-empty Korean string."""
        regime = detect_market_regime([], {}, {}, date(2026, 4, 10))
        self.assertIsInstance(regime.implication, str)
        # Even neutral has implication text
        self.assertIn("중립", regime.implication)

    def test_drivers_contain_required_keys(self) -> None:
        """Drivers dict should contain vix, trend, rates, breadth."""
        macro = {
            "vix": {"level": "18"},
            "spy_technicals": {"close": "480", "sma50": "475", "sma200": "460"},
            "us10y": {"level": "4.1", "change": "0.2"},
        }
        regime = detect_market_regime([], macro, {}, date(2026, 4, 10))
        for key in ("vix", "trend", "rates", "breadth", "risk_assets"):
            self.assertIn(key, regime.drivers, f"Missing driver key: {key}")

    def test_confidence_capped_at_100(self) -> None:
        """Even extreme scores should have confidence ≤ 100."""
        macro = {
            "vix": {"level": "10"},
            "spy_technicals": {"close": "550", "sma50": "500", "sma200": "450"},
            "us10y": {"level": "3.0", "change": "-3.0"},
            "copper": {"change": "2.0"},
        }
        collected = {
            f"T{i}": _make_ctd(price_vs_sma50="10.0")
            for i in range(10)
        }
        regime = detect_market_regime([], macro, collected, date(2026, 4, 10))
        self.assertLessEqual(regime.confidence, 100)
        self.assertEqual(regime.regime, "risk_on")

    def test_frozen_dataclass(self) -> None:
        """MarketRegime should be immutable."""
        regime = detect_market_regime([], {}, {}, date(2026, 4, 10))
        with self.assertRaises(AttributeError):
            regime.regime = "risk_on"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
