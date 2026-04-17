from __future__ import annotations

import csv
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


class BenchmarkAlphaTests(unittest.TestCase):
    """Survivorship-bias guard: watchlist equal-weight benchmark + alpha."""

    def test_alpha_computed_against_same_date_benchmark(self) -> None:
        # Stage two evaluated rows sharing a signal_date, then run update.
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "signal_tracker.csv"
            # Seed two signals on the same date with a price history that
            # produces returns of +2% (AAPL) and +6% (MSFT) at 5D.
            price_history = [
                {"date": "2026-04-01", "ticker": "AAPL", "price": "100.00 USD"},
                {"date": "2026-04-02", "ticker": "AAPL", "price": "100.00 USD"},
                {"date": "2026-04-03", "ticker": "AAPL", "price": "100.00 USD"},
                {"date": "2026-04-06", "ticker": "AAPL", "price": "100.00 USD"},
                {"date": "2026-04-07", "ticker": "AAPL", "price": "100.00 USD"},
                {"date": "2026-04-08", "ticker": "AAPL", "price": "102.00 USD"},
                {"date": "2026-04-01", "ticker": "MSFT", "price": "100.00 USD"},
                {"date": "2026-04-02", "ticker": "MSFT", "price": "100.00 USD"},
                {"date": "2026-04-03", "ticker": "MSFT", "price": "100.00 USD"},
                {"date": "2026-04-06", "ticker": "MSFT", "price": "100.00 USD"},
                {"date": "2026-04-07", "ticker": "MSFT", "price": "100.00 USD"},
                {"date": "2026-04-08", "ticker": "MSFT", "price": "106.00 USD"},
            ]

            for ticker in ("AAPL", "MSFT"):
                record_signals(
                    [TickerAnalysis(
                        ticker=ticker, name=ticker, date="2026-04-01",
                        summary="", key_news=[], news_references=[],
                        financial_highlights=[], risks_or_watchpoints=[],
                        signal_or_takeaway="", data_snapshot={}, news_tone={"label": "neutral"},
                    )],
                    date(2026, 4, 1),
                    {ticker: 100.0},
                    csv_path,
                )

            update_signal_returns(
                csv_path, date(2026, 4, 8),
                {"AAPL": 102.0, "MSFT": 106.0},
                price_history_rows=price_history,
            )

            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = {row["ticker"]: row for row in csv.DictReader(handle)}

            # Benchmark = mean(+2%, +6%) = +4%
            self.assertEqual(rows["AAPL"]["benchmark_return_5d"], "+4.00%")
            self.assertEqual(rows["MSFT"]["benchmark_return_5d"], "+4.00%")
            # Alpha = return - benchmark
            self.assertEqual(rows["AAPL"]["alpha_5d"], "-2.00%")
            self.assertEqual(rows["MSFT"]["alpha_5d"], "+2.00%")


class DirectionClassificationTests(unittest.TestCase):
    """Regression tests for the self-referential direction classifier fix.

    Prior to Step 4, `_classify_signal_direction` derived direction from
    `news_tone.label` as a fallback. `signal_track_record` then read that
    direction, creating a loop: news_tone → direction → track_record →
    next decision's news_tone-derived factor. We now prefer the decision
    layer's `action` which breaks the loop because `action` is produced
    downstream of (not by) news_tone within a single day's batch.
    """

    def test_action_buy_overrides_text_classification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "signal_tracker.csv"
            record_signals(
                [_analysis()],
                date(2026, 4, 8),
                {"AAPL": 100.0},
                csv_path,
                decisions=[TickerDecision(ticker="AAPL", action="avoid", conviction=30)],
                market_regime=MarketRegime(regime="risk_off"),
            )
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            # Despite bullish news_tone and "상승" wording, action=avoid → bear.
            self.assertEqual(rows[0]["signal_direction"], "bear")
            self.assertEqual(rows[0]["action"], "avoid")
            self.assertEqual(rows[0]["regime"], "risk_off")

    def test_action_watch_yields_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "signal_tracker.csv"
            record_signals(
                [_analysis()],
                date(2026, 4, 8),
                {"AAPL": 100.0},
                csv_path,
                decisions=[TickerDecision(ticker="AAPL", action="watch", conviction=50)],
            )
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["signal_direction"], "neutral")

    def test_factors_json_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "signal_tracker.csv"
            decision = TickerDecision(
                ticker="AAPL",
                action="buy",
                conviction=70,
                factors={"momentum": 12.5, "valuation": -3.0},
            )
            record_signals(
                [_analysis()], date(2026, 4, 8), {"AAPL": 100.0}, csv_path,
                decisions=[decision],
            )
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertIn("momentum", row["factors_json"])
            self.assertIn("valuation", row["factors_json"])

    def test_missing_decision_falls_back_to_text_classification(self) -> None:
        # Backward compat: when no decisions are passed, the text-based
        # classifier is still used (covers legacy test fixtures / failures).
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "signal_tracker.csv"
            record_signals([_analysis()], date(2026, 4, 8), {"AAPL": 100.0}, csv_path)
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["signal_direction"], "bull")
            self.assertEqual(rows[0]["action"], "")
            self.assertEqual(rows[0]["factors_json"], "")


class NeutralBandTests(unittest.TestCase):
    def _row(self, ticker: str, ret: float) -> dict[str, str]:
        return {"ticker": ticker, "evaluated_5d": "True", "return_5d": f"{ret:+.2f}%"}

    def test_band_scales_with_ticker_volatility(self) -> None:
        from src.utils.signal_tracker import build_ticker_neutral_bands

        rows = [self._row("CALM", r) for r in (0.8, -0.9, 1.0, -1.1, 0.95)]
        rows += [self._row("WILD", r) for r in (8.0, -9.5, 10.0, -11.0, 9.0)]
        bands = build_ticker_neutral_bands(rows)
        self.assertLess(bands["CALM"], bands["WILD"])
        self.assertLessEqual(bands["WILD"], 5.0)  # upper clamp
        self.assertGreaterEqual(bands["CALM"], 0.5)  # lower clamp

    def test_thin_sample_falls_back_to_default(self) -> None:
        from src.utils.signal_tracker import (
            DEFAULT_NEUTRAL_BAND_PCT,
            build_ticker_neutral_bands,
        )

        rows = [self._row("NEW", 0.5), self._row("NEW", -0.5)]
        bands = build_ticker_neutral_bands(rows)
        self.assertEqual(bands["NEW"], DEFAULT_NEUTRAL_BAND_PCT)

    def test_is_signal_win_respects_custom_band(self) -> None:
        from src.utils.signal_tracker import _is_signal_win

        # Without band → 3% movement fails the neutral test (default 1%).
        self.assertFalse(_is_signal_win("neutral", 3.0))
        # With a wider band (5%) → 3% counts as neutral "win".
        self.assertTrue(_is_signal_win("neutral", 3.0, neutral_band=5.0))
        # Directional classifications ignore the band entirely.
        self.assertTrue(_is_signal_win("bull", 0.1, neutral_band=5.0))
        self.assertFalse(_is_signal_win("bear", 0.1, neutral_band=5.0))


if __name__ == "__main__":
    unittest.main()
