from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.base import BaseCheck, CheckResult, Finding


class TestCheckResultShape(unittest.TestCase):
    def test_finding_is_frozen(self):
        f = Finding(ticker="AAPL", date=date(2026, 4, 28), module="research_note",
                    jsonpath="$.summary", detail={"reason": "x"})
        with self.assertRaises(Exception):
            f.ticker = "MSFT"  # type: ignore[misc]

    def test_check_result_pass_rate_clamped(self):
        cr = CheckResult(check_id="X", severity="pass", pass_rate=1.0,
                         findings=(), metrics={}, recommendation=None)
        self.assertEqual(cr.pass_rate, 1.0)

    def test_base_check_is_abstract(self):
        with self.assertRaises(TypeError):
            BaseCheck()  # type: ignore[abstract]


if __name__ == "__main__":
    unittest.main()
