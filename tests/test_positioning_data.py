from __future__ import annotations

import unittest

from src.collector.price import _format_fractional_percent, _map_recommendation


class PositioningDataTests(unittest.TestCase):
    def test_map_recommendation_uses_expected_boundaries(self) -> None:
        self.assertEqual(_map_recommendation(None), "N/A")
        self.assertEqual(_map_recommendation(1.4), "Strong Buy")
        self.assertEqual(_map_recommendation(2.0), "Buy")
        self.assertEqual(_map_recommendation(3.0), "Hold")
        self.assertEqual(_map_recommendation(4.2), "Sell")
        self.assertEqual(_map_recommendation(4.8), "Strong Sell")

    def test_format_fractional_percent_handles_decimal_inputs_for_positioning_fields(self) -> None:
        self.assertEqual(_format_fractional_percent(0.032), "3.20%")
        self.assertEqual(_format_fractional_percent(0.284), "28.40%")
        self.assertEqual(_format_fractional_percent(None), "N/A")


if __name__ == "__main__":
    unittest.main()
