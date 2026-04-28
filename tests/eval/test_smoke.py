from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import Any
from unittest import mock

from src.eval.checks.d1_semantic_drift import D1SemanticDrift
from src.eval.replay import LLMReplayClient
from src.eval.runner import RunnerConfig, run_audit
from tests.eval.fixtures.builders import make_dataset


class _StableClient(LLMReplayClient):
    def call(self, ticker: str, run_index: int) -> dict[str, Any]:
        return {"action": "buy", "summary": "stable.", "cost_usd": 0.05}


class TestSmokeAll14Checks(unittest.TestCase):
    def test_full_run_with_replay_overridden(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
            d1 = D1SemanticDrift(client=_StableClient(), replay_tickers=("AAPL",),
                                 runs_per_ticker=3, max_cost_usd=1.0, dry_run=False)
            cfg = RunnerConfig(
                root=tmp, audit_date=date(2026, 4, 28), window_days=14,
                tickers=["AAPL"],
                checks=("I1", "I2", "I3", "I4",
                        "O1", "O2", "O3", "O4", "O5",
                        "D1", "D2", "D3", "R1", "R2"),
                skip_replay=False, check_links=False,
                model_profile="economy", git_sha="abcd1234",
                check_overrides={"D1": d1},
            )
            with mock.patch("src.eval.runner.load_window", return_value=ds):
                exit_code, results = run_audit(cfg)
            self.assertEqual(len(results), 14)
            ids = {r.check_id for r in results}
            self.assertEqual(ids, {"I1", "I2", "I3", "I4", "O1", "O2", "O3", "O4",
                                   "O5", "D1", "D2", "D3", "R1", "R2"})
            json_path = tmp / "output" / "data" / "llm_audit" / "2026-04-28.json"
            self.assertTrue(json_path.exists())
            data = json.loads(json_path.read_text())
            self.assertEqual(data["summary"]["total_checks"], 14)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
