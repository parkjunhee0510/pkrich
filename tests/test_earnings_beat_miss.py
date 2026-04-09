from __future__ import annotations

import unittest

from src.collector.price import _classify_beat_miss, _derive_forward_eps, _format_growth_percentage, _format_surprise_percentage


class EarningsBeatMissTests(unittest.TestCase):
    def test_classify_beat_when_surprise_exceeds_five_percent(self) -> None:
        self.assertEqual(_classify_beat_miss("2.10", "2.00"), "beat")

    def test_classify_miss_when_surprise_below_negative_five_percent(self) -> None:
        self.assertEqual(_classify_beat_miss("1.80", "2.00"), "miss")

    def test_classify_inline_when_surprise_is_small(self) -> None:
        self.assertEqual(_classify_beat_miss("1.98", "2.00"), "in-line")

    def test_format_surprise_percentage_keeps_sign(self) -> None:
        self.assertEqual(_format_surprise_percentage("2.1277"), "+2.13%")

    def test_derive_forward_eps_from_price_and_forward_pe(self) -> None:
        self.assertEqual(_derive_forward_eps(120.0, "15"), "8.00")

    def test_format_growth_percentage_scales_decimal_ratios(self) -> None:
        self.assertEqual(_format_growth_percentage("0.124"), "+12.40% YoY")


if __name__ == "__main__":
    unittest.main()
