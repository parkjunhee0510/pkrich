from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.output.markdown import render_weekly_markdown
from src.types import NewsItem, TickerAnalysis
from src.utils.signal_tracker import record_signals, update_signal_returns
from src.utils.weekly_summary import load_weekly_summary


def _analysis(ticker: str, name: str, signal: str) -> TickerAnalysis:
    return TickerAnalysis(
        ticker=ticker,
        name=name,
        date="2026-04-08",
        summary=f"{name} summary",
        key_news=[f"{name} catalyst"],
        news_references=[
            NewsItem(title=f"{name} headline", source="Reuters", published_at="2026-04-08", link="https://example.com")
        ],
        financial_highlights=["시가총액: 1.00T"],
        risks_or_watchpoints=["리스크 체크"],
        signal_or_takeaway=signal,
        data_snapshot={"Price": "100.00 USD", "Daily Change": "+1.00%", "Sector": "Technology"},
        trade_frame={
            "entry_price": "현재가 $100.00",
            "stop_loss": "SMA50 $98.50",
            "target_1": "$105.00 (1.5×ATR)",
            "target_2": "애널리스트 목표 $120.00",
            "risk_reward_ratio": "1.5R",
            "position_size_note": "$10,000 계좌 1% 리스크 기준 약 30주",
            "bull_scenario": "상승 지속",
            "base_scenario": "박스권 소화",
            "bear_scenario": "하락 전환",
            "invalidation_price": "98.50 USD 아래",
            "watch_period": "향후 5거래일",
        },
        news_tone={"label": "bullish", "score": 1.0},
    )


def _write_sample_week(output_root: Path, trading_days: list[str]) -> None:
    data_dir = output_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    days = []
    market_prices = {
        "2026-04-02": ("98.00", "202.00"),
        "2026-04-03": ("99.00", "201.00"),
        "2026-04-06": ("100.00", "200.00"),
        "2026-04-07": ("105.00", "195.00"),
        "2026-04-08": ("110.00", "190.00"),
    }
    ticker_prices = {
        "2026-04-02": {"AAPL": "98.00 USD", "MSFT": "202.00 USD"},
        "2026-04-03": {"AAPL": "99.00 USD", "MSFT": "201.00 USD"},
        "2026-04-06": {"AAPL": "100.00 USD", "MSFT": "200.00 USD"},
        "2026-04-07": {"AAPL": "105.00 USD", "MSFT": "195.00 USD"},
        "2026-04-08": {"AAPL": "110.00 USD", "MSFT": "190.00 USD"},
    }

    for day in trading_days:
        sp500_price, ndx_price = market_prices[day]
        days.append(
            {
                "date": day,
                "market_overview": [
                    {"label": "S&P 500", "symbol": "^GSPC", "price": sp500_price, "change": "+0.10%"},
                    {"label": "NASDAQ 100", "symbol": "^NDX", "price": ndx_price, "change": "-0.10%"},
                ],
                "tickers": [
                    {
                        "ticker": "AAPL",
                        "name": "Apple Inc.",
                        "summary": "Apple summary",
                        "key_news": ["Apple AI catalyst"],
                        "news_references": [
                            {
                                "title": "Apple AI headline",
                                "source": "Reuters",
                                "published_at": day,
                                "link": "https://example.com/apple-ai",
                            }
                        ],
                        "signal_or_takeaway": "AAPL 상승 유지",
                        "data_snapshot": {
                            "Price": ticker_prices[day]["AAPL"],
                            "Daily Change": "+1.00%",
                            "Sector": "Technology",
                        },
                    },
                    {
                        "ticker": "MSFT",
                        "name": "Microsoft Corporation",
                        "summary": "Microsoft summary",
                        "key_news": ["Microsoft cloud catalyst"],
                        "news_references": [
                            {
                                "title": "Microsoft cloud headline",
                                "source": "Yahoo Finance",
                                "published_at": day,
                                "link": "https://example.com/msft-cloud",
                            }
                        ],
                        "signal_or_takeaway": "MSFT 조정 확인",
                        "data_snapshot": {
                            "Price": ticker_prices[day]["MSFT"],
                            "Daily Change": "-1.00%",
                            "Sector": "Technology",
                        },
                    },
                ],
            }
        )

    (data_dir / "dashboard.json").write_text(
        json.dumps({"days": days, "signal_stats": {}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (data_dir / "price_history.csv").write_text(
        "\n".join(
            [
                "date,ticker,price,daily_change,market_cap,trailing_pe,eps,52w_high,52w_low",
                *[
                    f"{day},AAPL,{ticker_prices[day]['AAPL']},+1.00%,1.00T,25.0,5.0,120.0,80.0"
                    for day in trading_days
                ],
                *[
                    f"{day},MSFT,{ticker_prices[day]['MSFT']},-1.00%,2.00T,30.0,6.0,240.0,150.0"
                    for day in trading_days
                ],
            ]
        ),
        encoding="utf-8",
    )


class WeeklySummaryTests(unittest.TestCase):
    def test_load_weekly_summary_aggregates_market_prices_news_actions_and_signals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            _write_sample_week(output_root, ["2026-04-02", "2026-04-03", "2026-04-06", "2026-04-07", "2026-04-08"])

            signal_csv = output_root / "data" / "signal_tracker.csv"
            record_signals(
                [
                    _analysis("AAPL", "Apple Inc.", "AAPL 상승 유지"),
                    _analysis("MSFT", "Microsoft Corporation", "MSFT 조정 확인"),
                ],
                date(2026, 4, 1),
                {"AAPL": 100.0, "MSFT": 200.0},
                signal_csv,
            )
            update_signal_returns(
                signal_csv,
                date(2026, 4, 8),
                {"AAPL": 110.0, "MSFT": 190.0},
                price_history_rows=[
                    {"date": "2026-04-02", "ticker": "AAPL", "price": "102.00 USD"},
                    {"date": "2026-04-03", "ticker": "AAPL", "price": "104.00 USD"},
                    {"date": "2026-04-06", "ticker": "AAPL", "price": "106.00 USD"},
                    {"date": "2026-04-07", "ticker": "AAPL", "price": "108.00 USD"},
                    {"date": "2026-04-02", "ticker": "MSFT", "price": "198.00 USD"},
                    {"date": "2026-04-03", "ticker": "MSFT", "price": "196.00 USD"},
                    {"date": "2026-04-06", "ticker": "MSFT", "price": "194.00 USD"},
                    {"date": "2026-04-07", "ticker": "MSFT", "price": "192.00 USD"},
                ],
            )

            summary = load_weekly_summary(date(2026, 4, 8), output_root=output_root)
            content = render_weekly_markdown(summary)

            self.assertEqual(summary.trading_days, 3)
            self.assertFalse(summary.is_partial)
            self.assertEqual(summary.market_moves[0].weekly_change, "+10.00%")
            self.assertEqual(summary.sector_performance[0].sector, "Technology")
            self.assertEqual(summary.sector_performance[0].average_weekly_change, "+2.50%")
            self.assertEqual(summary.top_gainers[0].ticker, "AAPL")
            self.assertEqual(summary.top_losers[0].ticker, "MSFT")
            self.assertEqual(summary.repeated_news[0].count, 3)
            self.assertEqual(summary.signal_validation_rows[0]["ticker"], "MSFT")
            self.assertIn("## 섹터 퍼포먼스", content)
            self.assertIn("## 주간 시장 개요", content)
            self.assertIn("## 종목별 주간 등락 요약", content)
            self.assertIn("## 이번 주 반복 노출 뉴스 요약", content)
            self.assertIn("## 시그널 검증 결과 (지난 20거래일)", content)
            self.assertIn("**bull 시그널 5일 승률: +100.00% (평균 +10.00%)**", content)
            self.assertIn("- [ ] AAPL: AAPL 상승 유지", content)

    def test_load_weekly_summary_marks_partial_week_when_less_than_three_days(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            _write_sample_week(output_root, ["2026-04-06", "2026-04-07"])

            summary = load_weekly_summary(date(2026, 4, 8), output_root=output_root)
            content = render_weekly_markdown(summary)

            self.assertTrue(summary.is_partial)
            self.assertEqual(summary.trading_days, 2)
            self.assertIn("데이터 축적 중", content)


if __name__ == "__main__":
    unittest.main()
