from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from src.collector.price import (
    _calc_atr_14d,
    _calc_gap_percent,
    _calc_price_vs_sma,
    _calc_relative_volume,
    _calc_rs_vs_benchmark,
    _calc_week52_position,
)


class _FakeFrame:
    def __init__(self, rows: list[dict[str, float | datetime]]) -> None:
        self._rows = rows
        self.empty = not rows
        self.index = [row["Date"] for row in rows]

    def __getitem__(self, key: str):
        return [row.get(key) for row in self._rows]


class PriceActionTests(unittest.TestCase):
    def test_calc_atr_14d_uses_true_range_average(self) -> None:
        start = datetime(2026, 3, 1)
        rows = []
        for idx in range(15):
            close = 100.0 + idx
            rows.append(
                {
                    "Date": start + timedelta(days=idx),
                    "High": close + 2.0,
                    "Low": close - 2.0,
                    "Close": close,
                }
            )
        atr = _calc_atr_14d(_FakeFrame(rows))
        self.assertAlmostEqual(atr or 0.0, 4.0, places=6)

    def test_calc_relative_volume_returns_multiple(self) -> None:
        self.assertEqual(_calc_relative_volume({"volume": 142_000_000, "averageVolume": 100_000_000}), "1.42x")

    def test_calc_gap_percent_uses_open_vs_previous_close(self) -> None:
        self.assertEqual(_calc_gap_percent(101.0, 100.0), "+1.00%")

    def test_calc_price_vs_sma_formats_percentage(self) -> None:
        self.assertEqual(_calc_price_vs_sma(103.2, 100.0), "+3.20%")

    def test_calc_week52_position_returns_percentile(self) -> None:
        self.assertEqual(_calc_week52_position(109.2, 120.0, 80.0), "73%")

    def test_calc_rs_vs_benchmark_uses_30d_delta(self) -> None:
        self.assertEqual(_calc_rs_vs_benchmark("+8.10%", 4.0), "+4.10%")


if __name__ == "__main__":
    unittest.main()
