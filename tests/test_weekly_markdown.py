from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.output.markdown import render_weekly_markdown
from src.utils.weekly_summary import load_weekly_summary


def _write_positive_week(output_root: Path) -> None:
    data_dir = output_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    days = [
        {
            "date": "2026-04-06",
            "market_overview": [{"label": "S&P 500", "symbol": "^GSPC", "price": "100.00", "change": "+0.10%"}],
            "tickers": [{"ticker": "AAPL", "name": "Apple Inc.", "signal_or_takeaway": "AAPL 유지"}],
        },
        {
            "date": "2026-04-07",
            "market_overview": [{"label": "S&P 500", "symbol": "^GSPC", "price": "101.00", "change": "+0.10%"}],
            "tickers": [{"ticker": "AAPL", "name": "Apple Inc.", "signal_or_takeaway": "AAPL 유지"}],
        },
        {
            "date": "2026-04-08",
            "market_overview": [{"label": "S&P 500", "symbol": "^GSPC", "price": "102.00", "change": "+0.10%"}],
            "tickers": [{"ticker": "AAPL", "name": "Apple Inc.", "signal_or_takeaway": "AAPL 유지"}],
        },
    ]

    (data_dir / "dashboard.json").write_text(json.dumps({"days": days}, ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "price_history.csv").write_text(
        "\n".join(
            [
                "date,ticker,price,daily_change,market_cap,trailing_pe,eps,52w_high,52w_low",
                "2026-04-06,AAPL,100.00 USD,+0.10%,1.00T,25.0,5.0,120.0,80.0",
                "2026-04-07,AAPL,101.00 USD,+0.10%,1.00T,25.0,5.0,120.0,80.0",
                "2026-04-08,AAPL,102.00 USD,+0.10%,1.00T,25.0,5.0,120.0,80.0",
            ]
        ),
        encoding="utf-8",
    )


class WeeklyMarkdownTests(unittest.TestCase):
    def test_render_weekly_markdown_reports_no_losers_when_all_tickers_are_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            _write_positive_week(output_root)

            summary = load_weekly_summary(date(2026, 4, 8), output_root=output_root)
            content = render_weekly_markdown(summary)

            self.assertEqual(summary.top_losers, [])
            self.assertIn("- 이번 주 하락 종목이 없습니다.", content)

    def test_render_weekly_markdown_includes_optional_weekly_insight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            _write_positive_week(output_root)

            with patch(
                "src.utils.weekly_summary._load_weekly_insight",
                return_value="기술주는 강세를 보였고 다음 주에는 실적 이벤트를 점검해야 합니다.",
            ):
                summary = load_weekly_summary(date(2026, 4, 8), output_root=output_root)
                content = render_weekly_markdown(summary)

            self.assertEqual(summary.weekly_insight, "기술주는 강세를 보였고 다음 주에는 실적 이벤트를 점검해야 합니다.")
            self.assertIn("## 주간 인사이트", content)


if __name__ == "__main__":
    unittest.main()
