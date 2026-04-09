from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.output.markdown import render_weekly_markdown
from src.utils.weekly_summary import load_weekly_summary


def _write_sample_week(output_root: Path, trading_days: list[str]) -> None:
    data_dir = output_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    days = []
    market_prices = {
        "2026-04-06": ("100.00", "200.00"),
        "2026-04-07": ("105.00", "195.00"),
        "2026-04-08": ("110.00", "190.00"),
    }
    ticker_prices = {
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
                        "key_news": ["애플 AI 뉴스"],
                        "news_references": [
                            {
                                "title": "Apple AI headline",
                                "source": "Reuters",
                                "published_at": day,
                                "link": "https://example.com/apple-ai",
                            }
                        ],
                        "signal_or_takeaway": "AAPL 점검",
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
                        "key_news": ["마이크로소프트 클라우드 뉴스"],
                        "news_references": [
                            {
                                "title": "Microsoft cloud headline",
                                "source": "Yahoo Finance",
                                "published_at": day,
                                "link": "https://example.com/msft-cloud",
                            }
                        ],
                        "signal_or_takeaway": "MSFT 점검",
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
        json.dumps({"days": days}, ensure_ascii=False, indent=2),
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
    def test_load_weekly_summary_aggregates_market_prices_news_and_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            _write_sample_week(output_root, ["2026-04-06", "2026-04-07", "2026-04-08"])

            summary = load_weekly_summary(date(2026, 4, 8), output_root=output_root)
            content = render_weekly_markdown(summary)

            self.assertEqual(summary.trading_days, 3)
            self.assertFalse(summary.is_partial)
            self.assertEqual(summary.market_moves[0].weekly_change, "+10.00%")
            self.assertEqual(summary.top_gainers[0].ticker, "AAPL")
            self.assertEqual(summary.top_losers[0].ticker, "MSFT")
            self.assertEqual(summary.repeated_news[0].count, 3)
            self.assertIn("## 주간 시장 개요", content)
            self.assertIn("## 종목별 주간 등락 요약", content)
            self.assertIn("## 이번 주 반복 노출 뉴스 요약", content)
            self.assertIn("- [ ] AAPL: AAPL 점검", content)

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
