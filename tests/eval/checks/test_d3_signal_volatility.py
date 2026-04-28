from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.d3_signal_volatility import D3SignalVolatility
from tests.eval.fixtures.builders import make_dataset


class TestD3(unittest.TestCase):
    def test_pass_when_signal_stable(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for record in ds.daily["AAPL"].values():
            record["payload"]["llm_signals"] = {"narrative_strength": 0.6}
        result = D3SignalVolatility().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_signal_swings(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        days = sorted(ds.daily["AAPL"].keys())
        for i, d in enumerate(days):
            ds.daily["AAPL"][d]["payload"]["llm_signals"] = {
                "narrative_strength": 0.0 if i % 2 else 1.0
            }
        result = D3SignalVolatility().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
