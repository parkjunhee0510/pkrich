from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.backtester.engine import build_backtest_summary


CSV_BODY = """signal_date,ticker,signal_type,signal_direction,signal_price,catalyst_tag,news_tone,trade_frame_scenario,return_1d,return_5d,return_20d,evaluated_1d,evaluated_5d,evaluated_20d
2026-04-01,AAPL,takeaway,bull,100,earnings,bullish,base,+1.00%,+2.00%,+5.00%,True,True,True
2026-04-02,MSFT,takeaway,bull,200,earnings,neutral,base,+0.50%,+1.00%,-2.00%,True,True,True
2026-04-03,TSLA,takeaway,bear,300,macro,bearish,base,-1.00%,-3.00%,-6.00%,True,True,True
"""

PENDING_CSV_BODY = """signal_date,ticker,signal_type,signal_direction,signal_price,catalyst_tag,news_tone,trade_frame_scenario,return_1d,return_5d,return_20d,evaluated_1d,evaluated_5d,evaluated_20d
2026-04-10,AAPL,takeaway,bull,100,earnings,bullish,base,+1.00%,+2.00%,N/A,True,True,False
2026-04-11,MSFT,takeaway,bear,200,earnings,neutral,base,+0.50%,+1.00%,N/A,True,True,False
"""


class BacktesterTests(unittest.TestCase):
    def test_build_backtest_summary_returns_bull_bear_and_ticker_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "signal_tracker.csv"
            csv_path.write_text(CSV_BODY, encoding="utf-8")

            summary = build_backtest_summary(csv_path)

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["signals"], 3)
        self.assertEqual(summary["win_rate"], "66.7%")
        self.assertEqual(summary["best_return"], "+6.00%")
        self.assertEqual(summary["worst_return"], "-2.00%")
        self.assertEqual(summary["bull"]["signals"], 2)
        self.assertEqual(summary["bear"]["signals"], 1)
        self.assertEqual(summary["bear"]["avg_return"], "+6.00%")
        self.assertEqual(summary["ticker_rows"][0]["ticker"], "TSLA")
        self.assertGreaterEqual(len(summary["equity_curve"]), 2)

    def test_build_backtest_summary_reports_pending_evaluation_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "signal_tracker.csv"
            csv_path.write_text(PENDING_CSV_BODY, encoding="utf-8")

            summary = build_backtest_summary(csv_path)

        self.assertEqual(summary["status"], "awaiting_evaluation")
        self.assertEqual(summary["signals"], 0)
        self.assertEqual(summary["pending_signals"], 2)
        self.assertEqual(summary["first_eval_date"], "2026-05-08")
        self.assertIn("2026-05-08", summary["message"])


if __name__ == "__main__":
    unittest.main()
