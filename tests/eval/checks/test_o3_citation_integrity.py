from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.o3_citation_integrity import O3CitationIntegrity
from tests.eval.fixtures.builders import make_dataset


class TestO3(unittest.TestCase):
    def test_pass_when_key_news_in_references(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        result = O3CitationIntegrity(check_links=False).run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_orphan_key_news(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for d, record in ds.daily["AAPL"].items():
            record["payload"]["key_news"] = ["Completely fabricated headline"]
            record["payload"]["news_references"] = [
                {"title": "Real headline", "source": "x", "published_at": "2026-01-01",
                 "link": "https://x"}
            ]
        result = O3CitationIntegrity(check_links=False).run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
