from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from src.eval.runner import run_audit, RunnerConfig
from tests.eval.fixtures.builders import make_dataset


class TestRunner(unittest.TestCase):
    def test_skip_replay_runs_all_registered_checks(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
            cfg = RunnerConfig(
                root=tmp, audit_date=date(2026, 4, 28),
                window_days=14, tickers=["AAPL"],
                checks=("I1",), skip_replay=True,
                model_profile="economy", git_sha="abcd1234",
            )
            with mock.patch("src.eval.runner.load_window", return_value=ds):
                exit_code, results = run_audit(cfg)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].check_id, "I1")
            md = tmp / "docs" / "reports" / "llm-audit-2026-04-28.md"
            jp = tmp / "output" / "data" / "llm_audit" / "2026-04-28.json"
            self.assertTrue(md.exists())
            self.assertTrue(jp.exists())
            self.assertEqual(exit_code, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_check_isolation_one_fails_others_continue(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))

            class _Boom:
                check_id = "BOOM"
                dimension = "boom"

                def run(self, ds):
                    raise RuntimeError("synthetic")

            cfg = RunnerConfig(
                root=tmp, audit_date=date(2026, 4, 28),
                window_days=14, tickers=["AAPL"],
                checks=("I1", "BOOM"), skip_replay=True,
                model_profile="economy", git_sha="abcd1234",
                check_overrides={"BOOM": _Boom()},
            )
            with mock.patch("src.eval.runner.load_window", return_value=ds):
                exit_code, results = run_audit(cfg)
            ids = {r.check_id for r in results}
            self.assertEqual(ids, {"I1", "BOOM"})
            boom = next(r for r in results if r.check_id == "BOOM")
            self.assertEqual(boom.severity, "fail")
            self.assertNotEqual(exit_code, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_invalid_window_raises(self):
        cfg = RunnerConfig(
            root=Path("/tmp"), audit_date=date(2026, 4, 28),
            window_days=0, tickers=["AAPL"],
            checks=("I1",), skip_replay=True,
            model_profile="economy", git_sha="x",
        )
        with self.assertRaises(ValueError):
            run_audit(cfg)

    def test_replay_cost_meta_uses_d1_metric(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))

            class _D1:
                check_id = "D1"
                dimension = "semantic_drift"

                def run(self, ds):
                    from src.eval.checks.base import CheckResult
                    return CheckResult(
                        check_id="D1",
                        severity="pass",
                        pass_rate=1.0,
                        findings=(),
                        metrics={"actual_cost_usd": 0.42},
                        recommendation=None,
                    )

            cfg = RunnerConfig(
                root=tmp, audit_date=date(2026, 4, 28),
                window_days=14, tickers=["AAPL"],
                checks=("D1",), skip_replay=False,
                model_profile="economy", git_sha="abcd1234",
                check_overrides={"D1": _D1()},
            )
            with mock.patch("src.eval.runner.load_window", return_value=ds):
                run_audit(cfg)
            data = __import__("json").loads(
                (tmp / "output" / "data" / "llm_audit" / "2026-04-28.json").read_text()
            )
            self.assertEqual(data["replay"]["cost_usd"], 0.42)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
