import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tests.fixtures.risk_intel_fixtures import ai_sector_payload, nvda_watchlist, policy_payload
from src.output.health_check import check_output_health
from src.output.risk_intel_builder import build_risk_intel_artifacts


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _mirror_dir(root: Path) -> Path:
    mirror = root / "web" / "public" / "output" / "data"
    mirror.mkdir(parents=True, exist_ok=True)
    return mirror


def _write_valid_risk_intel_outputs(root: Path) -> None:
    from src.output.risk_intel_json import write_risk_intel_outputs

    (root / "web").mkdir(exist_ok=True)
    write_risk_intel_outputs(
        output_root=root / "output",
        project_root=root,
        run_date=date(2026, 5, 19),
        policy_payload=policy_payload(),
        search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
        watchlist=nvda_watchlist(),
        portfolio_summary=None,
        sector_payload=ai_sector_payload(),
    )


def _copy_risk_intel_mirror(source: Path, mirror: Path) -> None:
    mirror.mkdir(parents=True, exist_ok=True)
    for filename in ("risk_intel_graph.json", "risk_intel_summary.json", "risk_intel_refresh_log.json"):
        (mirror / filename).write_bytes((source / filename).read_bytes())


def _current_graph_run_id(root: Path) -> str:
    graph_path = root / "output" / "data" / "risk_intel_graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    return str(graph["generation"]["run_id"])


def _insert_refresh_request(
    root: Path,
    *,
    patch_candidate_json: str = "{}",
    validation_result_json: str = "{}",
) -> None:
    db_path = root / "output" / "data" / "risk_intel.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO risk_intel_refresh_requests (
              refresh_id,
              base_graph_run_id,
              node_id,
              patch_status,
              patch_candidate_json,
              validation_result_json,
              requested_at,
              expires_at,
              applied_run_id,
              review_note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "refresh:test",
                _current_graph_run_id(root),
                "ticker:NVDA",
                "pending",
                patch_candidate_json,
                validation_result_json,
                "2026-05-19T00:00:00+09:00",
                "2026-05-20T00:00:00+09:00",
                None,
                None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


class RiskIntelHealthTest(unittest.TestCase):
    def test_valid_risk_intel_artifacts_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            mirror = root / "web" / "public" / "output" / "data"
            result = check_output_health(root, web_data_dir=mirror)
            self.assertTrue(result.ok, result.format_summary())

    def test_missing_risk_intel_sqlite_fails_after_json_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            (root / "output" / "data" / "risk_intel.sqlite").unlink()

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            self.assertFalse(result.ok)
            self.assertIn("risk_intel_sqlite_missing", result.format_summary())

    def test_newer_sqlite_run_than_public_json_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            db_path = root / "output" / "data" / "risk_intel.sqlite"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO risk_intel_runs (
                      run_id,
                      as_of,
                      status,
                      schema_version,
                      generated_at,
                      scoring_config_version,
                      confidence_config_version,
                      source_config_version,
                      created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "run:2026-05-20-risk-intel",
                        "2026-05-20",
                        "ok",
                        "1.0.0",
                        "2026-05-20T00:00:00+09:00",
                        "risk-intel-scoring-v1",
                        "risk-intel-confidence-v1",
                        "risk-intel-sources-v1",
                        "2026-05-20T00:00:00+09:00",
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            self.assertFalse(result.ok)
            self.assertIn("risk_intel_sqlite_run_mismatch", result.format_summary())
            self.assertIn("latest sqlite run does not match public graph run", result.format_summary())

    def test_sqlite_run_metadata_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            run_id = _current_graph_run_id(root)
            db_path = root / "output" / "data" / "risk_intel.sqlite"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    UPDATE risk_intel_runs
                    SET generated_at = ?
                    WHERE run_id = ?
                    """,
                    ("2026-05-19T00:01:00+09:00", run_id),
                )
                conn.commit()
            finally:
                conn.close()

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            self.assertFalse(result.ok)
            self.assertIn("risk_intel_sqlite_run_mismatch", result.format_summary())
            self.assertIn("sqlite run generated_at does not match public graph", result.format_summary())

    def test_manifest_hash_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            summary_path = root / "output" / "data" / "risk_intel_summary.json"
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            payload["counts"]["cards"] = 999
            _write(summary_path, payload)

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            self.assertFalse(result.ok)
            self.assertIn("risk_intel_manifest_mismatch", result.format_summary())

    def test_sqlite_is_not_allowed_in_web_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            mirror_db = root / "web" / "public" / "output" / "data" / "risk_intel.sqlite"
            mirror_db.write_bytes(b"not allowed")

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            self.assertFalse(result.ok)
            self.assertIn("risk_intel_sqlite_mirrored", result.format_summary())

    def test_sqlite_mirror_check_honors_custom_web_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            source = root / "output" / "data"
            custom_mirror = root / "custom_mirror"
            _copy_risk_intel_mirror(source, custom_mirror)
            (custom_mirror / "risk_intel.sqlite").write_bytes(b"not allowed")

            result = check_output_health(root, web_data_dir=custom_mirror)

            self.assertFalse(result.ok)
            self.assertIn("risk_intel_sqlite_mirrored", result.format_summary())

    def test_invalid_sqlite_json_column_fails_health_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            db_path = root / "output" / "data" / "risk_intel.sqlite"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    UPDATE risk_intel_nodes
                    SET aliases_json = ?
                    WHERE rowid = (SELECT rowid FROM risk_intel_nodes LIMIT 1)
                    """,
                    ("{bad-json",),
                )
                conn.commit()
            finally:
                conn.close()

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            self.assertFalse(result.ok)
            self.assertIn("risk_intel_sqlite_json_invalid", result.format_summary())

    def test_refresh_request_patch_candidate_invalid_json_fails_health_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            _insert_refresh_request(root, patch_candidate_json="{bad-json")

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            summary = result.format_summary()
            self.assertFalse(result.ok)
            self.assertIn("risk_intel_sqlite_json_invalid", summary)
            self.assertIn("risk_intel_refresh_requests refresh:test patch_candidate_json invalid JSON", summary)

    def test_refresh_request_validation_result_wrong_shape_fails_health_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            _insert_refresh_request(root, validation_result_json="[]")

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            summary = result.format_summary()
            self.assertFalse(result.ok)
            self.assertIn("risk_intel_sqlite_json_invalid", summary)
            self.assertIn("risk_intel_refresh_requests refresh:test validation_result_json must be dict", summary)

    def test_bad_alert_path_numeric_field_reports_issue_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            graph_path = root / "output" / "data" / "risk_intel_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["alert_paths"][0]["score"] = "bad-number"
            _write(graph_path, graph)

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            self.assertFalse(result.ok)
            self.assertIn("invalid_risk_intel_graph", result.format_summary())

    def test_alert_path_nan_raw_score_reports_issue_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            graph_path = root / "output" / "data" / "risk_intel_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["alert_paths"][0]["raw_score"] = "NaN"
            _write(graph_path, graph)

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            summary = result.format_summary()
            self.assertFalse(result.ok)
            self.assertIn("invalid_risk_intel_graph", summary)
            self.assertIn("alert path raw_score must be a finite number between 0 and 1", summary)

    def test_alert_path_infinite_cap_value_reports_issue_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            graph_path = root / "output" / "data" / "risk_intel_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["alert_paths"][0]["caps_applied"] = ["inference_only_cap"]
            graph["alert_paths"][0]["cap_value"] = "Infinity"
            _write(graph_path, graph)

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            summary = result.format_summary()
            self.assertFalse(result.ok)
            self.assertIn("invalid_risk_intel_graph", summary)
            self.assertIn("alert path cap_value must be a finite number between 0 and 1", summary)

    def test_alert_path_score_outside_probability_range_reports_issue_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            graph_path = root / "output" / "data" / "risk_intel_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["alert_paths"][0]["score"] = 1.5
            _write(graph_path, graph)

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            summary = result.format_summary()
            self.assertFalse(result.ok)
            self.assertIn("invalid_risk_intel_graph", summary)
            self.assertIn("alert path score must be a finite number between 0 and 1", summary)

    def test_manifest_path_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_risk_intel_outputs(root)
            graph = json.loads((root / "output" / "data" / "risk_intel_graph.json").read_text(encoding="utf-8"))
            db_path = root / "output" / "data" / "risk_intel.sqlite"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    UPDATE risk_intel_export_manifest
                    SET path = ?
                    WHERE run_id = ? AND artifact_name = ?
                    """,
                    ("wrong_dir/risk_intel_graph.json", graph["generation"]["run_id"], "risk_intel_graph"),
                )
                conn.commit()
            finally:
                conn.close()

            result = check_output_health(root, web_data_dir=root / "web" / "public" / "output" / "data")

            self.assertFalse(result.ok)
            self.assertIn("risk_intel_manifest_mismatch", result.format_summary())

    def test_inferred_edge_missing_inference_refs_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = build_risk_intel_artifacts(
                run_date=date(2026, 5, 19),
                policy_payload=policy_payload(),
                search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
                watchlist=nvda_watchlist(),
                portfolio_summary=None,
                sector_payload=ai_sector_payload(),
            )
            artifacts["graph"]["edges"][0]["evidence_type"] = "inferred"
            artifacts["graph"]["edges"][0]["inference_refs"] = []
            _write(root / "output" / "data" / "risk_intel_graph.json", artifacts["graph"])
            result = check_output_health(root, web_data_dir=_mirror_dir(root))
            self.assertFalse(result.ok)
            self.assertIn("invalid_risk_intel_graph", result.format_summary())

    def test_summary_graph_run_id_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = build_risk_intel_artifacts(
                run_date=date(2026, 5, 19),
                policy_payload=policy_payload(),
                search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
                watchlist=nvda_watchlist(),
                portfolio_summary=None,
                sector_payload=ai_sector_payload(),
            )
            artifacts["summary"]["derived_from_graph_run_id"] = "run:mismatch"
            data = root / "output" / "data"
            _write(data / "risk_intel_graph.json", artifacts["graph"])
            _write(data / "risk_intel_summary.json", artifacts["summary"])
            result = check_output_health(root, web_data_dir=_mirror_dir(root))
            self.assertFalse(result.ok)
            self.assertIn("risk_intel_run_id_mismatch", result.format_summary())

    def test_edge_confidence_outside_configured_band_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = build_risk_intel_artifacts(
                run_date=date(2026, 5, 19),
                policy_payload=policy_payload(),
                search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
                watchlist=nvda_watchlist(),
                portfolio_summary=None,
                sector_payload=ai_sector_payload(),
            )
            artifacts["graph"]["edges"][0]["evidence_type"] = "inferred"
            artifacts["graph"]["edges"][0]["confidence"] = 0.95
            _write(root / "output" / "data" / "risk_intel_graph.json", artifacts["graph"])
            result = check_output_health(root, web_data_dir=_mirror_dir(root))
            self.assertFalse(result.ok)
            self.assertIn("edge confidence must match configured band", result.format_summary())

    def test_promoted_stale_domain_rule_requires_degraded_status_and_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = build_risk_intel_artifacts(
                run_date=date(2026, 5, 19),
                policy_payload=policy_payload(),
                search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
                watchlist=nvda_watchlist(),
                portfolio_summary=None,
                sector_payload=ai_sector_payload(),
            )
            artifacts["graph"]["domain_rules"][0]["last_reviewed"] = "2024-01-01"
            artifacts["graph"]["status"] = "ok"
            artifacts["graph"]["health_warnings"] = []
            _write(root / "output" / "data" / "risk_intel_graph.json", artifacts["graph"])
            result = check_output_health(root, web_data_dir=_mirror_dir(root))
            self.assertFalse(result.ok)
            self.assertIn("promoted stale domain rule requires degraded status", result.format_summary())


if __name__ == "__main__":
    unittest.main()
