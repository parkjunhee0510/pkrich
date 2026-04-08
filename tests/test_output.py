from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.output.markdown import append_price_history, render_daily_markdown, render_ticker_markdown
from src.types import NewsItem, TickerAnalysis


def _sample_analysis() -> TickerAnalysis:
    return TickerAnalysis(
        ticker="AAPL",
        name="Apple Inc.",
        date="2026-04-08",
        summary="Sample summary.",
        key_news=["Headline 1"],
        news_references=[
            NewsItem(
                title="Headline 1",
                source="Reuters",
                published_at="2026-04-08",
                link="https://example.com/headline-1",
            )
        ],
        financial_highlights=["Market cap: 1.00T"],
        risks_or_watchpoints=["Watch competition."],
        signal_or_takeaway="Stay on watch.",
        data_snapshot={
            "Price": "100.00 USD",
            "Daily Change": "+1.23%",
            "Market Cap": "1.00T",
            "Trailing P/E": "25.00",
            "Sector": "Technology",
        },
    )


class OutputTests(unittest.TestCase):
    def _top_news_section(self, content: str) -> str:
        return content.split("## Top News Links", 1)[1].split("## Action Items", 1)[0]

    def test_render_daily_markdown_keeps_expected_sections(self) -> None:
        content = render_daily_markdown([_sample_analysis()], date(2026, 4, 8))

        self.assertIn("# Daily Research - 2026-04-08", content)
        self.assertIn("## Market Overview", content)
        self.assertIn("## Watchlist Summary", content)
        self.assertIn("## Top Movers", content)
        self.assertIn("## Top News Links", content)
        self.assertIn("### Technology", content)
        self.assertIn("**AAPL**: [Headline 1](https://example.com/headline-1)", content)
        self.assertIn("## Action Items", content)

    def test_render_daily_markdown_orders_news_links_by_date_within_sector(self) -> None:
        newer = _sample_analysis()
        older = TickerAnalysis(
            ticker="MSFT",
            name="Microsoft Corporation",
            date="2026-04-08",
            summary="Another summary.",
            key_news=["Headline 2"],
            news_references=[
                NewsItem(
                    title="Headline 2",
                    source="Reuters",
                    published_at="2026-04-07",
                    link="https://example.com/headline-2",
                )
            ],
            financial_highlights=["Market cap: 2.00T"],
            risks_or_watchpoints=["Watch cloud demand."],
            signal_or_takeaway="Stay on watch.",
            data_snapshot={
                "Price": "200.00 USD",
                "Daily Change": "+0.50%",
                "Market Cap": "2.00T",
                "Trailing P/E": "30.00",
                "Sector": "Technology",
            },
        )

        content = render_daily_markdown([older, newer], date(2026, 4, 8))
        top_news_section = self._top_news_section(content)

        self.assertLess(top_news_section.find("**AAPL**"), top_news_section.find("**MSFT**"))

    def test_render_daily_markdown_uses_source_priority_when_dates_match(self) -> None:
        yahoo_item = TickerAnalysis(
            ticker="MSFT",
            name="Microsoft Corporation",
            date="2026-04-08",
            summary="Microsoft summary.",
            key_news=["Headline 2"],
            news_references=[
                NewsItem(
                    title="Headline 2",
                    source="Yahoo Finance",
                    published_at="2026-04-08",
                    link="https://example.com/headline-2",
                )
            ],
            financial_highlights=["Market cap: 2.00T"],
            risks_or_watchpoints=["Watch cloud demand."],
            signal_or_takeaway="Stay on watch.",
            data_snapshot={
                "Price": "200.00 USD",
                "Daily Change": "+0.50%",
                "Market Cap": "2.00T",
                "Trailing P/E": "30.00",
                "Sector": "Technology",
            },
        )

        reuters_item = _sample_analysis()

        content = render_daily_markdown([yahoo_item, reuters_item], date(2026, 4, 8))
        top_news_section = self._top_news_section(content)

        self.assertLess(top_news_section.find("**AAPL**"), top_news_section.find("**MSFT**"))

    def test_render_daily_markdown_uses_configurable_source_priority(self) -> None:
        original_output_config = Path("config/output.yaml").read_text(encoding="utf-8")
        try:
            Path("config/output.yaml").write_text(
                "\n".join(
                    [
                        "news_source_priority:",
                        "  Reuters: 1",
                        "  Yahoo Finance: 10",
                    ]
                ),
                encoding="utf-8",
            )

            yahoo_item = TickerAnalysis(
                ticker="MSFT",
                name="Microsoft Corporation",
                date="2026-04-08",
                summary="Microsoft summary.",
                key_news=["Headline 2"],
                news_references=[
                    NewsItem(
                        title="Headline 2",
                        source="Yahoo Finance",
                        published_at="2026-04-08",
                        link="https://example.com/headline-2",
                    )
                ],
                financial_highlights=["Market cap: 2.00T"],
                risks_or_watchpoints=["Watch cloud demand."],
                signal_or_takeaway="Stay on watch.",
                data_snapshot={
                    "Price": "200.00 USD",
                    "Daily Change": "+0.50%",
                    "Market Cap": "2.00T",
                    "Trailing P/E": "30.00",
                    "Sector": "Technology",
                },
            )

            reuters_item = _sample_analysis()
            content = render_daily_markdown([reuters_item, yahoo_item], date(2026, 4, 8))
            top_news_section = self._top_news_section(content)

            self.assertLess(top_news_section.find("**MSFT**"), top_news_section.find("**AAPL**"))
        finally:
            Path("config/output.yaml").write_text(original_output_config, encoding="utf-8")

    def test_render_ticker_markdown_keeps_expected_sections(self) -> None:
        content = render_ticker_markdown(_sample_analysis())

        self.assertIn("# AAPL - 2026-04-08", content)
        self.assertIn("## Summary", content)
        self.assertIn("## Key News", content)
        self.assertIn("[Headline 1](https://example.com/headline-1)", content)
        self.assertIn("## Financial Highlights", content)
        self.assertIn("## Risks / Watchpoints", content)
        self.assertIn("## Data Snapshot", content)
        self.assertIn("## Signal / Takeaway", content)

    def test_append_price_history_replaces_same_day_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "price_history.csv"

            append_price_history(csv_path, [_sample_analysis()])
            append_price_history(csv_path, [_sample_analysis()])

            with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["ticker"], "AAPL")
            self.assertEqual(rows[0]["date"], "2026-04-08")


if __name__ == "__main__":
    unittest.main()
