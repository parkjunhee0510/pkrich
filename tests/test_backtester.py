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

_HEADER = (
    "signal_date,ticker,signal_type,signal_direction,signal_price,catalyst_tag,"
    "news_tone,trade_frame_scenario,return_1d,return_5d,return_20d,"
    "evaluated_1d,evaluated_5d,evaluated_20d\n"
)


def _row(signal_date: str, ticker: str, direction: str, return_20d: str) -> str:
    return (
        f"{signal_date},{ticker},takeaway,{direction},100,earnings,bullish,base,"
        f"+1.00%,+2.00%,{return_20d},True,True,True\n"
    )


# Two bull signals on the SAME date, each +50%. They are held concurrently, so the
# portfolio return for that 20-day window is the equal-weight average (+50%), NOT
# the sequential product (1.5 * 1.5 = +125%).
CONCURRENT_CSV_BODY = _HEADER + _row("2026-04-01", "AAA", "bull", "+50.00%") + _row(
    "2026-04-01", "BBB", "bull", "+50.00%"
)

# Two bull signals in SEPARATE 20-trading-day windows (April vs July), each +50%.
# Non-overlapping windows compound across windows: 1.5 * 1.5 = +125%.
SEPARATE_WINDOWS_CSV_BODY = _HEADER + _row("2026-04-01", "AAA", "bull", "+50.00%") + _row(
    "2026-07-01", "BBB", "bull", "+50.00%"
)


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
        self.assertEqual(summary["message"], "Backtest statistics begin after 2026-05-08; pending signals: 2.")
        self.assertEqual(summary["strategy"], "Evaluate bull/bear signals on a 20-trading-day horizon.")


    def test_concurrent_signals_average_within_window_instead_of_compounding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "signal_tracker.csv"
            csv_path.write_text(CONCURRENT_CSV_BODY, encoding="utf-8")

            summary = build_backtest_summary(csv_path)

        # Equal-weight average of the concurrent window, not 1.5 * 1.5 = +125%.
        self.assertEqual(summary["cumulative_return"], "+50.00%")
        self.assertEqual(summary["bull"]["cumulative_return"], "+50.00%")
        self.assertEqual(summary["equity_curve"][-1]["cumulative_return"], "+50.00%")
        self.assertEqual(summary["equity_curve"][-1]["equity_multiple"], 1.5)

    def test_separate_windows_compound_across_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "signal_tracker.csv"
            csv_path.write_text(SEPARATE_WINDOWS_CSV_BODY, encoding="utf-8")

            summary = build_backtest_summary(csv_path)

        # Two non-overlapping 20-trading-day windows compound: 1.5 * 1.5 = +125%.
        self.assertEqual(summary["cumulative_return"], "+125.00%")
        self.assertEqual(summary["equity_curve"][-1]["cumulative_return"], "+125.00%")
        self.assertEqual(summary["equity_curve"][-1]["equity_multiple"], 2.25)

    def test_equity_curve_endpoint_matches_summary_cumulative_return(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "signal_tracker.csv"
            csv_path.write_text(CSV_BODY, encoding="utf-8")

            summary = build_backtest_summary(csv_path)

        self.assertEqual(
            summary["equity_curve"][-1]["cumulative_return"],
            summary["cumulative_return"],
        )


if __name__ == "__main__":
    unittest.main()
