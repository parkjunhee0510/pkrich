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
        "signal_or_takeaway": "Watch closely.",
        "earnings_setup": {},
        "news_references": [],
        "committee_analysis": {
            "status": "economy_only",
            "agreement_status": "aligned",
            "deep_review_triggered": False,
            "deep_review_reasons": [],
            "roles": {
                "pm": {
                    "stance": "watch",
                    "summary": "PM summary",
                    "valid": True,
                }
            },
        },
    }


def _pm_view() -> dict:
    return {
        "as_of": "2026-04-13",
        "swap_candidates": [
            {
                "held_ticker": "NVDA",
                "candidate_ticker": "AVGO",
                "swap_candidate_score": 44,
                "summary": "Review NVDA against AVGO within Technology exposure.",
                "reasons": ["AVGO conviction is higher."],
                "overlap_context": "Same sector: Technology",
                "review_points": ["Check relative conviction support."],
            }
        ],
        "event_exposure_items": [
            {
                "ticker": "NVDA",
                "event_risk_score": 31,
                "event_label": "Earnings",
                "event_date": "2026-04-15",
                "days_until": 2,
                "summary": "Review NVDA event exposure before earnings.",
                "reasons": ["Earnings is scheduled in D-2."],
                "review_points": ["Check event sizing."],
            }
        ],
        "today_priority_queue": [
            {
                "priority_type": "swap_review",
                "ticker": "NVDA",
                "related_ticker": "AVGO",
                "today_priority_score": 52,
                "summary": "Review NVDA against AVGO within Technology exposure.",
                "reasons": ["AVGO conviction is higher."],
                "destination": "portfolio",
            }
        ],
        "empty_states": {
            "swap_candidates": "",
            "event_exposure_items": "",
            "today_priority_queue": "",
        },
    }


def _day(date: str, tickers: list[dict]) -> dict:
    return {
        "date": date,
        "market_overview": [{"label": "S&P 500", "value": "5000"}],
        "macro_context": {"vix": 15.0},
        "market_regime": {"regime": "neutral"},
        "pm_view": _pm_view(),
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
                weekly_summary={"schema_version": SCHEMA_VERSION, "weekly_insight": "summary"},
            )

            index = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["schema_version"], SCHEMA_VERSION)
            self.assertEqual(index["date"], "2026-04-13")
            self.assertEqual(len(index["tickers"]), 1)
            self.assertEqual(index["signal_stats"], {"recent_signals": []})
            self.assertEqual(index["weekly_summary"]["weekly_insight"], "summary")
            self.assertEqual(index["pm_view"]["swap_candidates"][0]["candidate_ticker"], "AVGO")
            self.assertEqual(index["pm_view"]["event_exposure_items"][0]["event_label"], "Earnings")
            summary = index["tickers"][0]
            self.assertEqual(summary["ticker"], "AAPL")
            self.assertIn("data_snapshot", summary)
            self.assertIn("news_references", summary)
            self.assertIn("earnings_setup", summary)
            self.assertIn("committee_analysis", summary)
            self.assertEqual(summary["committee_analysis"]["roles"]["pm"]["summary"], "PM summary")
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
