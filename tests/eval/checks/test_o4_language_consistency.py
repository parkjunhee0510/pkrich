from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.o4_language_consistency import O4LanguageConsistency
from tests.eval.fixtures.builders import make_dataset


class TestO4(unittest.TestCase):
    def test_pass_when_consistent_korean(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for record in ds.daily["AAPL"].values():
            record["payload"]["summary"] = "애플은 100달러에 거래되고 있습니다."
        result = O4LanguageConsistency().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_swings_between_languages(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        days = sorted(ds.daily["AAPL"].keys())
        for i, d in enumerate(days):
            if i % 2:
                ds.daily["AAPL"][d]["payload"]["summary"] = "Apple traded at 100 USD today."
            else:
                ds.daily["AAPL"][d]["payload"]["summary"] = "애플은 100달러에 거래되었습니다."
        result = O4LanguageConsistency().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
