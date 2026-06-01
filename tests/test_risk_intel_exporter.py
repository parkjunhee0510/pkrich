import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.output.risk_intel_builder import build_risk_intel_artifacts
from src.output.risk_intel_exporter import export_risk_intel_artifacts
from src.output.risk_intel_store import replace_graph_run
from tests.fixtures.risk_intel_fixtures import ai_sector_payload, nvda_watchlist, policy_payload


class RiskIntelExporterTest(unittest.TestCase):
    def test_exports_public_json_contract_from_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "risk_intel.sqlite"
            artifacts = build_risk_intel_artifacts(
                run_date=date(2026, 5, 19),
                policy_payload=policy_payload(),
                search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
                watchlist=nvda_watchlist(),
                portfolio_summary=None,
                sector_payload=ai_sector_payload(),
            )
            replace_graph_run(db_path, artifacts)

            exported = export_risk_intel_artifacts(db_path)

            self.assertEqual(set(exported), {"graph", "summary", "refresh_log"})
            self.assertEqual(exported["graph"]["generation"]["run_id"], artifacts["graph"]["generation"]["run_id"])
            self.assertEqual(exported["summary"]["derived_from_graph_run_id"], exported["graph"]["generation"]["run_id"])
            self.assertEqual(exported["refresh_log"]["generation"]["run_id"], exported["graph"]["generation"]["run_id"])
            self.assertGreaterEqual(len(exported["summary"]["cards"]), 1)
            self.assertEqual(exported["summary"]["cards"][0]["score"], exported["graph"]["alert_paths"][0]["score"])


if __name__ == "__main__":
    unittest.main()
