from __future__ import annotations

import unittest

from src.collector.news_rss import _merge_news_items
from src.types import NewsItem


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


if __name__ == "__main__":
    unittest.main()
