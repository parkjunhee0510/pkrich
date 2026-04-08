from __future__ import annotations

import unittest

from src.collector.news_rss import _merge_news_items
from src.collector.news_search import build_news_query
from src.types import NewsItem
from src.types import WatchlistItem


class NewsCollectionTests(unittest.TestCase):
    def test_merge_news_items_deduplicates_and_limits(self) -> None:
        primary = [
            NewsItem(title="Apple launches new service", source="RSS"),
            NewsItem(title="Apple launches new service", source="RSS"),
        ]
        supplemental = [
            NewsItem(title="Analysts revisit Apple outlook", source="DuckDuckGo"),
            NewsItem(title="Apple shares rise after event", source="DuckDuckGo"),
        ]

        merged = _merge_news_items(primary, supplemental, max_items=2)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].title, "Apple launches new service")
        self.assertEqual(merged[1].title, "Analysts revisit Apple outlook")

    def test_build_news_query_includes_finance_context_and_keywords(self) -> None:
        query = build_news_query(
            WatchlistItem(
                ticker="NVDA",
                name="NVIDIA Corporation",
                sector="Semiconductors",
                keywords=["GPU", "data center", "AI chips"],
            )
        )

        self.assertIn("NVDA", query)
        self.assertIn("NVIDIA", query)
        self.assertIn("stock", query)
        self.assertIn("GPU", query)
        self.assertIn("data center", query)
        self.assertIn("earnings guidance analyst upgrade downgrade outlook", query)


if __name__ == "__main__":
    unittest.main()
