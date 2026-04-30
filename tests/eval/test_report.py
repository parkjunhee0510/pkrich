from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.eval.checks.base import CheckResult
from src.eval.report import render_markdown, render_json, write_artifacts


def _result(check_id="I1", severity="pass", pass_rate=1.0):
    return CheckResult(check_id=check_id, severity=severity, pass_rate=pass_rate,
                       findings=(), metrics={"foo": 0.0}, recommendation=None)


class TestRender(unittest.TestCase):
    def test_render_json_has_required_keys(self):
        out = render_json(
            audit_date=date(2026, 4, 28),
            window_start=date(2026, 4, 15),
            window_end=date(2026, 4, 28),
            tickers=("AAPL",),
            model_profile="economy",
            git_sha="abcd1234",
            replay_meta={"enabled": False, "tickers": [], "runs_per_ticker": 0,
                         "cost_usd": 0.0, "cost_cap_usd": 1.0},
            results=[_result()],
        )
        self.assertEqual(out["schema_version"], 1)
        self.assertEqual(out["summary"]["total_checks"], 1)
        self.assertEqual(out["summary"]["info"], 0)
        self.assertIn("checks", out)
        self.assertEqual(out["checks"][0]["dimension"], "schema_stability")
        self.assertIn("thresholds", out["checks"][0])
        self.assertEqual(out["checks"][0]["sample_count"], 0)

    def test_render_markdown_contains_verdict_matrix(self):
        md = render_markdown(
            audit_date=date(2026, 4, 28),
            window_start=date(2026, 4, 15),
            window_end=date(2026, 4, 28),
            tickers=("AAPL",),
            replay_meta={"enabled": False, "cost_usd": 0.0},
            results=[_result(severity="warn", pass_rate=0.91)],
        )
        self.assertIn("# LLM Audit Report", md)
        self.assertIn("Verdict Matrix", md)
        self.assertIn("I1", md)

    def test_write_artifacts_creates_files(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            md_path, json_path = write_artifacts(
                root=tmp, audit_date=date(2026, 4, 28),
                window_start=date(2026, 4, 15), window_end=date(2026, 4, 28),
                tickers=("AAPL",), model_profile="economy", git_sha="abcd1234",
                replay_meta={"enabled": False, "tickers": [], "runs_per_ticker": 0,
                             "cost_usd": 0.0, "cost_cap_usd": 1.0},
                results=[_result()],
            )
            self.assertTrue(md_path.exists())
            self.assertTrue(json_path.exists())
            data = json.loads(json_path.read_text())
            self.assertEqual(data["schema_version"], 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
