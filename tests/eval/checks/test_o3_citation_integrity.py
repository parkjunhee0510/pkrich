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

    def test_check_links_measures_head_success_rate(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for record in ds.daily["AAPL"].values():
            record["payload"]["key_news"] = ["headline"]
            record["payload"]["news_references"] = [
                {"title": "headline", "source": "x", "published_at": "2026-01-01", "link": "https://ok"},
                {"title": "headline", "source": "x", "published_at": "2026-01-01", "link": "https://bad"},
            ]
        result = O3CitationIntegrity(
            check_links=True,
            link_checker=lambda url: url.endswith("/ok"),
        ).run(ds)
        self.assertEqual(result.metrics["link_success_rate"], 0.5)
        self.assertEqual(result.severity, "fail")

    def test_pass_when_key_news_has_explicit_source_titles(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for record in ds.daily["AAPL"].values():
            record["payload"]["key_news"] = ["요약된 한국어 뉴스"]
            record["payload"]["key_news_source_titles"] = ["Exact source headline"]
            record["payload"]["news_references"] = [
                {"title": "Exact source headline", "source": "x", "published_at": "2026-01-01", "link": "https://x"}
            ]

        result = O3CitationIntegrity(check_links=False).run(ds)

        self.assertEqual(result.severity, "pass")


if __name__ == "__main__":
    unittest.main()
