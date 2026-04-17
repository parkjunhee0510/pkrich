from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.output.sharded_export import SCHEMA_VERSION, write_sharded_outputs


def _ticker_payload(ticker: str, date: str, price: str) -> dict:
    return {
        "ticker": ticker,
        "name": f"{ticker} Corp.",
        "date": date,
        "summary": f"{ticker} summary",
        "data_snapshot": {"Price": price, "Daily Change": "+1.00%"},
        "news_tone": {"label": "neutral"},
        "period_changes": {"7d": "N/A", "30d": "N/A"},
        "signal_or_takeaway": "관찰",
        "earnings_setup": {},
        "news_references": [],
    }


def _day(date: str, tickers: list[dict]) -> dict:
    return {
        "date": date,
        "market_overview": [{"label": "S&P 500", "value": "5000"}],
        "macro_context": {"vix": 15.0},
        "market_regime": {"regime": "neutral"},
        "portfolio_risk": {},
        "portfolio_summary": None,
        "tickers": tickers,
    }


class ShardedExportTests(unittest.TestCase):
    def test_index_contains_summary_not_full_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            latest = _day("2026-04-13", [_ticker_payload("AAPL", "2026-04-13", "100.00 USD")])

            write_sharded_outputs(
                data_dir,
                latest,
                [latest],
                signal_stats={"recent_signals": []},
                weekly_summary={"schema_version": SCHEMA_VERSION, "weekly_insight": "요약"},
            )

            index = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["schema_version"], SCHEMA_VERSION)
            self.assertEqual(index["date"], "2026-04-13")
            self.assertEqual(len(index["tickers"]), 1)
            self.assertEqual(index["signal_stats"], {"recent_signals": []})
            self.assertEqual(index["weekly_summary"]["weekly_insight"], "요약")
            summary = index["tickers"][0]
            self.assertEqual(summary["ticker"], "AAPL")
            self.assertIn("data_snapshot", summary)
            self.assertIn("news_references", summary)
            self.assertIn("earnings_setup", summary)
            self.assertNotIn("quarterly_financials", summary)

    def test_per_ticker_latest_and_history_emitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            day1 = _day("2026-04-10", [_ticker_payload("AAPL", "2026-04-10", "98.00 USD")])
            day2 = _day("2026-04-13", [_ticker_payload("AAPL", "2026-04-13", "100.00 USD")])

            write_sharded_outputs(data_dir, day2, [day1, day2])

            latest = json.loads((data_dir / "tickers" / "AAPL" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["schema_version"], SCHEMA_VERSION)
            self.assertEqual(latest["ticker"], "AAPL")
            self.assertEqual(latest["payload"]["data_snapshot"]["Price"], "100.00 USD")

            history = json.loads((data_dir / "tickers" / "AAPL" / "history.json").read_text(encoding="utf-8"))
            self.assertEqual(history["ticker"], "AAPL")
            self.assertEqual([d["date"] for d in history["days"]], ["2026-04-10", "2026-04-13"])

    def test_multiple_tickers_shard_independently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            latest = _day(
                "2026-04-13",
                [
                    _ticker_payload("AAPL", "2026-04-13", "100.00 USD"),
                    _ticker_payload("MSFT", "2026-04-13", "300.00 USD"),
                ],
            )

            write_sharded_outputs(data_dir, latest, [latest])

            self.assertTrue((data_dir / "tickers" / "AAPL" / "latest.json").exists())
            self.assertTrue((data_dir / "tickers" / "MSFT" / "latest.json").exists())
            self.assertTrue((data_dir / "tickers" / "AAPL" / "history.json").exists())
            self.assertTrue((data_dir / "tickers" / "MSFT" / "history.json").exists())


if __name__ == "__main__":
    unittest.main()
