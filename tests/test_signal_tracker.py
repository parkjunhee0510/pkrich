from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.types import MarketRegime, NewsItem, TickerAnalysis, TickerDecision
from src.utils.signal_tracker import load_recent_signals, load_signal_stats, record_signals, update_signal_returns


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
            "entry_price": "현재가 $100.00",
            "stop_loss": "SMA50 $98.50",
            "target_1": "$105.00 (1.5×ATR)",
            "target_2": "애널리스트 목표 $120.00",
            "risk_reward_ratio": "1.5R",
            "position_size_note": "$10,000 계좌 1% 리스크 기준 약 30주",
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

    def test_record_signals_writes_lf_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "signal_tracker.csv"
            record_signals([_analysis()], date(2026, 4, 8), {"AAPL": 100.0}, csv_path)

            contents = csv_path.read_bytes()

        self.assertIn(b"\n", contents)
        self.assertNotIn(b"\r", contents)

    def test_record_signals_persists_decision_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "signal_tracker.csv"
            decision = TickerDecision(
                ticker="AAPL",
                action="buy",
                conviction=72,
                raw_conviction=80,
                factors={"momentum": 1.5, "valuation": -0.5},
                factor_reasoning={"momentum": "price trend improved"},
                confidence_meta={"data_quality_score": 0.88},
            )
            regime = MarketRegime(regime="risk_on", sub_regime="growth", confidence=70)

            record_signals(
                [_analysis()],
                date(2026, 4, 8),
                {"AAPL": 100.0},
                csv_path,
                decisions=[decision],
                market_regime=regime,
            )

            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(rows[0]["action"], "buy")
        self.assertEqual(rows[0]["conviction"], "72")
        self.assertEqual(rows[0]["raw_conviction"], "80")
        self.assertEqual(rows[0]["regime"], "risk_on")
        self.assertEqual(rows[0]["sub_regime"], "growth")
        self.assertEqual(json.loads(rows[0]["factors_json"]), {"momentum": 1.5, "valuation": -0.5})
        self.assertEqual(json.loads(rows[0]["factor_reasoning_json"]), {"momentum": "price trend improved"})
        self.assertEqual(json.loads(rows[0]["confidence_meta_json"]), {"data_quality_score": 0.88})

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

    def test_load_recent_signals_returns_latest_prompt_friendly_rows(self) -> None:
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

            history = load_recent_signals(csv_path, "AAPL", limit=1)

            self.assertEqual(len(history), 1)
            # load_recent_signals returns prompt-friendly short keys:
            # "date" (not "signal_date"), "direction" (not "signal_direction")
            self.assertEqual(history[0]["date"], "2026-04-01")
            self.assertEqual(history[0]["direction"], "bull")
            self.assertEqual(history[0]["return_5d"], "+5.00%")


if __name__ == "__main__":
    unittest.main()
