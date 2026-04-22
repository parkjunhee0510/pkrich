from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from src.decision.registry import FactorRegistry, build_factor_registry


class DecisionRegistryTests(unittest.TestCase):
    def test_registry_discovers_expected_factor_names(self) -> None:
        config = {
            "valuation": {"max": 20},
            "momentum": {"max": 20},
            "catalyst_recency": {"min": -10, "max": 20},
            "signal_track_record": {"min": -10, "max": 15},
            "news_tone": {"min": -5, "max": 10},
            "regime_adjustment": {"min": -15, "max": 15},
            "earnings_pattern": {"min": -10, "max": 10},
            "fundamentals": {"max": 10},
            "portfolio_risk": {"min": -10, "max": 0},
            "macro_event": {"min": -8, "max": 6},
            "macro_regime": {"min": -6, "max": 8},
            "peer_rank": {"min": -4, "max": 8},
        }
        registry = build_factor_registry(config)
        self.assertEqual(
            registry.names(),
            {
                "valuation",
                "momentum",
                "catalyst_recency",
                "signal_track_record",
                "news_tone",
                "regime_adjustment",
                "earnings_pattern",
                "fundamentals",
                "portfolio_risk",
                "macro_event",
                "macro_regime",
                "peer_rank",
            },
        )

    def test_registry_fails_when_config_missing_factor(self) -> None:
        with self.assertRaises(ValueError):
            build_factor_registry({"valuation": {"max": 20}})

    def test_registry_rejects_duplicate_name(self) -> None:
        registry = FactorRegistry()
        config = {
            "valuation": {"max": 20},
            "momentum": {"max": 20},
            "catalyst_recency": {"min": -10, "max": 20},
            "signal_track_record": {"min": -10, "max": 15},
            "news_tone": {"min": -5, "max": 10},
            "regime_adjustment": {"min": -15, "max": 15},
            "earnings_pattern": {"min": -10, "max": 10},
            "fundamentals": {"max": 10},
            "portfolio_risk": {"min": -10, "max": 0},
            "macro_event": {"min": -8, "max": 6},
            "macro_regime": {"min": -6, "max": 8},
            "peer_rank": {"min": -4, "max": 8},
        }
        registry.discover(config)
        factor = registry.all()[0]
        with self.assertRaises(ValueError):
            registry.register(factor)


if __name__ == "__main__":
    unittest.main()
