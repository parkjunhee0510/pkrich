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


class BacktesterTests(unittest.TestCase):
    def test_build_backtest_summary_uses_bull_signals_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "signal_tracker.csv"
            csv_path.write_text(CSV_BODY, encoding="utf-8")

            summary = build_backtest_summary(csv_path)

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["signals"], 2)
        self.assertEqual(summary["win_rate"], "50.0%")
        self.assertEqual(summary["best_return"], "+5.00%")
        self.assertEqual(summary["worst_return"], "-2.00%")


if __name__ == "__main__":
    unittest.main()
