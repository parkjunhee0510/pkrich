from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.types import NewsItem, TickerAnalysis
from src.utils.signal_tracker import load_signal_stats, record_signals, update_signal_returns


def _analysis() -> TickerAnalysis:
    return TickerAnalysis(
        ticker="AAPL",
        name="Apple Inc.",
        date="2026-04-08",
        summary="Summary",
        key_news=["Apple earnings beat expectations"],
        news_references=[
            NewsItem(
                title="[실적] Apple Inc., 10-Q 분기 실적 관련 보고서를 SEC에 제출",
                source="SEC EDGAR",
                published_at="2026-04-08",
                link="https://example.com/sec",
                form_type="10-Q",
                catalyst_type="hard",
                importance_score=200,
            )
        ],
        financial_highlights=["시가총액: 1.00T"],
        risks_or_watchpoints=["Risk check"],
        signal_or_takeaway="상승 모멘텀이 유지되는지 점검",
        data_snapshot={"Price": "100.00 USD", "Daily Change": "+1.00%"},
        trade_frame={
            "bull_scenario": "상승 지속",
            "base_scenario": "박스권 소화",
            "bear_scenario": "이동평균 이탈",
            "invalidation_price": "98.50 USD 아래",
            "watch_period": "향후 5거래일",
        },
        news_tone={"label": "bullish", "score": 1.0},
    )


class SignalTrackerTests(unittest.TestCase):
    def test_record_signals_creates_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "signal_tracker.csv"
            record_signals([_analysis()], date(2026, 4, 8), {"AAPL": 100.0}, csv_path)

            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["signal_direction"], "bull")
            self.assertEqual(rows[0]["catalyst_tag"], "실적")

    def test_update_signal_returns_uses_trading_day_horizons(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "signal_tracker.csv"
            record_signals([_analysis()], date(2026, 4, 1), {"AAPL": 100.0}, csv_path)

            history_rows = [
                {"date": "2026-04-01", "ticker": "AAPL", "price": "100.00 USD"},
                {"date": "2026-04-02", "ticker": "AAPL", "price": "101.00 USD"},
                {"date": "2026-04-03", "ticker": "AAPL", "price": "98.00 USD"},
                {"date": "2026-04-06", "ticker": "AAPL", "price": "102.00 USD"},
                {"date": "2026-04-07", "ticker": "AAPL", "price": "103.00 USD"},
                {"date": "2026-04-08", "ticker": "AAPL", "price": "104.00 USD"},
            ]

            updated = update_signal_returns(
                csv_path,
                date(2026, 4, 9),
                {"AAPL": 106.0},
                price_history_rows=history_rows,
            )
            stats = load_signal_stats(csv_path)

            self.assertEqual(updated, 1)
            recent = stats["recent_signals"][0]
            self.assertEqual(recent["return_1d"], "+1.00%")
            self.assertEqual(recent["return_5d"], "+4.00%")
            self.assertEqual(recent["return_20d"], "N/A")
            self.assertEqual(recent["evaluated_1d"], "True")
            self.assertEqual(recent["evaluated_5d"], "True")
            self.assertEqual(recent["evaluated_20d"], "False")

    def test_load_signal_stats_builds_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "signal_tracker.csv"
            record_signals([_analysis()], date(2026, 4, 1), {"AAPL": 100.0}, csv_path)
            update_signal_returns(
                csv_path,
                date(2026, 4, 9),
                {"AAPL": 105.0},
                price_history_rows=[
                    {"date": "2026-04-01", "ticker": "AAPL", "price": "100.00 USD"},
                    {"date": "2026-04-02", "ticker": "AAPL", "price": "101.00 USD"},
                    {"date": "2026-04-03", "ticker": "AAPL", "price": "102.00 USD"},
                    {"date": "2026-04-06", "ticker": "AAPL", "price": "103.00 USD"},
                    {"date": "2026-04-07", "ticker": "AAPL", "price": "104.00 USD"},
                ],
            )

            stats = load_signal_stats(csv_path)

            bull_summary = stats["summary_by_direction"]["bull"]
            self.assertEqual(bull_summary["count"], 1)
            self.assertEqual(bull_summary["evaluated_5d"], 1)
            self.assertEqual(bull_summary["win_rate_5d"], "+100.00%")
            self.assertEqual(bull_summary["avg_return_5d"], "+5.00%")


if __name__ == "__main__":
    unittest.main()
