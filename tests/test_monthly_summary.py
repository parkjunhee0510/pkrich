from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.utils.monthly_summary import load_monthly_summary


class MonthlySummaryTests(unittest.TestCase):
    def test_load_monthly_summary_aggregates_latest_month(self) -> None:
        payload = {
            "days": [
                {
                    "date": "2026-04-01",
                    "tickers": [
                        {"ticker": "AAPL", "data_snapshot": {"Daily Change": "+1.00%"}},
                        {"ticker": "MSFT", "data_snapshot": {"Daily Change": "-0.50%"}},
                    ],
                },
                {
                    "date": "2026-04-02",
                    "tickers": [
                        {"ticker": "AAPL", "data_snapshot": {"Daily Change": "+2.00%"}, "fundamentals": {"sector": "Tech"}},
                        {"ticker": "MSFT", "data_snapshot": {"Daily Change": "+1.00%"}, "fundamentals": {"sector": "Tech"}},
                    ],
                },
            ]
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = Path(tmp_dir) / "output"
            data_dir = output_root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "dashboard.json").write_text(json.dumps(payload), encoding="utf-8")

            summary = load_monthly_summary(date(2026, 4, 10), output_root=output_root)

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["month"], "2026-04")
        self.assertEqual(summary["trading_days"], 2)
        self.assertEqual(summary["top_tickers"][0]["ticker"], "AAPL")


if __name__ == "__main__":
    unittest.main()
