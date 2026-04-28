from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.o1_schema_compliance import O1SchemaCompliance
from tests.eval.fixtures.builders import make_dataset


class TestO1(unittest.TestCase):
    def test_pass_when_all_required_fields_present(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        result = O1SchemaCompliance().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_summary_is_int(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        ds.daily["AAPL"][ds.window_end]["payload"]["summary"] = 42
        result = O1SchemaCompliance().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
