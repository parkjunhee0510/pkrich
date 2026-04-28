from __future__ import annotations

import os
import unittest
from datetime import date
from pathlib import Path

from src.eval.checks.base import CheckResult
from src.eval.report import render_markdown


GOLDEN_PATH = Path(__file__).parent / "fixtures" / "golden" / "audit_report_sample.md"


def _fixture_results():
    return [
        CheckResult(check_id="I1", severity="pass", pass_rate=1.0,
                    findings=(), metrics={"missing_field_rate": 0.0}, recommendation=None),
        CheckResult(check_id="I3", severity="fail", pass_rate=0.33,
                    findings=(), metrics={"format_count": 3.0},
                    recommendation="Normalize ISO."),
    ]


class TestGolden(unittest.TestCase):
    def test_markdown_matches_golden(self):
        md = render_markdown(
            audit_date=date(2026, 4, 28),
            window_start=date(2026, 4, 15), window_end=date(2026, 4, 28),
            tickers=("AAPL", "MSFT"),
            replay_meta={"enabled": False, "cost_usd": 0.0},
            results=_fixture_results(),
        )
        if os.environ.get("UPDATE_GOLDENS") == "1":
            GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            GOLDEN_PATH.write_text(md, encoding="utf-8")
        expected = GOLDEN_PATH.read_text(encoding="utf-8")
        self.assertEqual(md, expected)


if __name__ == "__main__":
    unittest.main()
