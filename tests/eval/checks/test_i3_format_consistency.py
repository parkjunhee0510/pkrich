from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.i3_format_consistency import I3FormatConsistency
from tests.eval.fixtures.builders import make_dataset


class TestI3(unittest.TestCase):
    def test_pass_when_uniform_iso(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        result = I3FormatConsistency().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_warn_when_two_formats(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        bad_day = ds.window_end
        ds.daily["AAPL"][bad_day]["payload"]["news_references"] = [
            {"title": "x", "source": "Reuters",
             "published_at": "Fri, 30 Jan 2026 08:00:00 GMT", "link": "https://x"},
        ]
        result = I3FormatConsistency().run(ds)
        self.assertEqual(result.severity, "warn")

    def test_fail_with_three_formats(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        days = sorted(ds.daily["AAPL"].keys())
        ds.daily["AAPL"][days[0]]["payload"]["news_references"] = [
            {"title": "a", "source": "x", "published_at": "2026-04-15", "link": "https://x"},
        ]
        ds.daily["AAPL"][days[1]]["payload"]["news_references"] = [
            {"title": "b", "source": "x", "published_at": "Fri, 30 Jan 2026 08:00:00 GMT",
             "link": "https://x"},
        ]
        ds.daily["AAPL"][days[2]]["payload"]["news_references"] = [
            {"title": "c", "source": "x", "published_at": "20/04/2026", "link": "https://x"},
        ]
        result = I3FormatConsistency().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
