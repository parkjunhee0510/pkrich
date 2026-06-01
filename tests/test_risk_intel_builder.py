import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.output.risk_intel_builder import _health_warnings, _status_from_inputs, build_risk_intel_artifacts
from tests.fixtures.risk_intel_fixtures import (
    ai_sector_payload,
    held_nvda_portfolio,
    nvda_watchlist,
    policy_payload,
)


def _latest_sqlite_run_id(data_dir: Path) -> str | None:
    db_path = data_dir / "risk_intel.sqlite"
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            """
            SELECT run_id
            FROM risk_intel_runs
            ORDER BY as_of DESC, generated_at DESC, run_id DESC
            LIMIT 1
            """
        ).fetchone()
    return str(row[0]) if row else None


class RiskIntelBuilderTest(unittest.TestCase):
    def test_builds_graph_summary_and_refresh_log_from_policy_payload(self) -> None:
        artifacts = build_risk_intel_artifacts(
            run_date=date(2026, 5, 19),
            policy_payload=policy_payload(),
            search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
            watchlist=nvda_watchlist(),
            portfolio_summary=held_nvda_portfolio(),
            sector_payload=ai_sector_payload(),
        )

        graph = artifacts["graph"]
        summary = artifacts["summary"]
        refresh_log = artifacts["refresh_log"]

        self.assertEqual(graph["schema_version"], "1.0.0")
        self.assertEqual(graph["generation"]["run_id"], "run:2026-05-19-risk-intel")
        self.assertEqual(summary["derived_from_graph_run_id"], graph["generation"]["run_id"])
        self.assertEqual(refresh_log["generation"]["run_id"], graph["generation"]["run_id"])
        self.assertTrue(any(node["id"] == "ticker:NVDA" for node in graph["nodes"]))
        self.assertTrue(any(edge["evidence_refs"] for edge in graph["edges"]))
        self.assertGreaterEqual(len(graph["alert_paths"]), 1)
        self.assertEqual(summary["cards"][0]["alert_level_label_ko"], "경보")
        self.assertEqual(summary["cards"][0]["score"], graph["alert_paths"][0]["score"])
        self.assertEqual(summary["cards"][0]["raw_score"], graph["alert_paths"][0]["raw_score"])
        self.assertEqual(summary["cards"][0]["score_kind"], graph["alert_paths"][0]["score_kind"])
        self.assertEqual(summary["cards"][0]["caps_applied"], graph["alert_paths"][0]["caps_applied"])
        self.assertEqual(summary["cards"][0]["guardrails_applied"], graph["alert_paths"][0]["guardrails_applied"])
        self.assertEqual(summary["cards"][0]["affected_tickers"][0]["exposure_label_ko"], "보유")
        self.assertTrue(summary["cards"][0]["affected_tickers"][0]["is_holding"])

    def test_watchlist_only_card_marks_interest_exposure(self) -> None:
        artifacts = build_risk_intel_artifacts(
            run_date=date(2026, 5, 19),
            policy_payload=policy_payload(),
            search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
            watchlist=nvda_watchlist(),
            portfolio_summary=None,
            sector_payload=ai_sector_payload(),
        )
        card = artifacts["summary"]["cards"][0]
        self.assertEqual(card["affected_tickers"][0]["exposure_label_ko"], "관심")
        self.assertFalse(card["affected_tickers"][0]["is_holding"])

    def test_status_is_partial_when_only_optional_inputs_are_not_present(self) -> None:
        input_status = [
            {"name": "policy_impact", "required": True, "status": "present"},
            {"name": "search_evidence", "required": True, "status": "present"},
            {"name": "portfolio", "required": True, "status": "present"},
            {"name": "watchlist", "required": True, "status": "present"},
            {"name": "sector_exposure", "required": True, "status": "present"},
            {"name": "social_signals", "required": False, "status": "skipped_not_enabled"},
        ]
        self.assertEqual(_status_from_inputs(input_status, [], {}, []), "partial")

    def test_stale_domain_rule_used_by_warning_degrades_status_and_warning(self) -> None:
        domain_rules = {
            "rule:stale": {
                "id": "rule:stale",
                "last_reviewed": "2024-01-01",
                "rule_confidence": 0.75,
            }
        }
        alert_paths = [{"alert_level": "warning", "inference_refs": ["rule:stale"]}]
        warnings = _health_warnings(
            input_status=[],
            pending_duplicate_candidates=[],
            domain_rules=domain_rules,
            alert_paths=alert_paths,
            as_of="2026-05-19",
        )
        self.assertTrue(any(item["code"] == "stale_domain_rule_promoted" for item in warnings))
        self.assertEqual(_status_from_inputs([], alert_paths, domain_rules, warnings), "degraded")

    def test_health_warnings_include_cache_and_pending_duplicate_context(self) -> None:
        warnings = _health_warnings(
            input_status=[{"name": "search_evidence", "status": "cache_only"}],
            pending_duplicate_candidates=[{"new_candidate_id": "issue:duplicate"}],
            domain_rules={},
            alert_paths=[],
            as_of="2026-05-19",
        )
        codes = {item["code"] for item in warnings}
        self.assertIn("input_cache_only", codes)
        self.assertIn("pending_duplicate_candidate", codes)

    def test_missing_required_payloads_errors_gracefully(self) -> None:
        artifacts = build_risk_intel_artifacts(
            run_date=date(2026, 5, 19),
            policy_payload=None,
            search_evidence_payload=None,
            watchlist=[],
            portfolio_summary=None,
            sector_payload=None,
        )
        self.assertEqual(artifacts["graph"]["status"], "error")
        self.assertEqual(artifacts["summary"]["cards"], [])
        policy_status = next(row for row in artifacts["graph"]["input_status"] if row["name"] == "policy_impact")
        self.assertEqual(policy_status["status"], "missing")

    def test_mixed_inferred_and_explicit_path_is_not_inference_only_capped(self) -> None:
        artifacts = build_risk_intel_artifacts(
            run_date=date(2026, 5, 19),
            policy_payload=policy_payload(),
            search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
            watchlist=nvda_watchlist(),
            portfolio_summary=None,
            sector_payload=ai_sector_payload(),
        )
        path = artifacts["graph"]["alert_paths"][0]
        self.assertNotIn("inference_only_cap", path["caps_applied"])
        self.assertEqual(set(path["edge_evidence_types"]), {"inferred", "explicit"})

    def test_writer_creates_three_artifacts_and_web_mirror(self) -> None:
        from src.output.risk_intel_json import write_risk_intel_outputs

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "web").mkdir()
            artifacts = write_risk_intel_outputs(
                output_root=root / "output",
                project_root=root,
                run_date=date(2026, 5, 19),
                policy_payload=policy_payload(),
                search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
                watchlist=nvda_watchlist(),
                portfolio_summary=None,
                sector_payload=ai_sector_payload(),
            )
            data_dir = root / "output" / "data"
            mirror_dir = root / "web" / "public" / "output" / "data"
            self.assertTrue((data_dir / "risk_intel_graph.json").is_file())
            self.assertTrue((data_dir / "risk_intel_summary.json").is_file())
            self.assertTrue((data_dir / "risk_intel_refresh_log.json").is_file())
            self.assertTrue((data_dir / "risk_intel.sqlite").is_file())
            self.assertFalse((mirror_dir / "risk_intel.sqlite").exists())
            self.assertFalse((mirror_dir / "risk_intel.sqlite-wal").exists())
            run_id = artifacts["graph"]["generation"]["run_id"]
            with closing(sqlite3.connect(data_dir / "risk_intel.sqlite")) as conn:
                rows = conn.execute(
                    """
                    SELECT artifact_name, sha256, byte_size
                    FROM risk_intel_export_manifest
                    WHERE run_id = ?
                    """,
                    (run_id,),
                ).fetchall()
            manifest = {
                row[0]: {
                    "sha256": row[1],
                    "byte_size": row[2],
                }
                for row in rows
            }
            expected_artifacts = {
                "risk_intel_graph": "risk_intel_graph.json",
                "risk_intel_summary": "risk_intel_summary.json",
                "risk_intel_refresh_log": "risk_intel_refresh_log.json",
            }
            self.assertEqual(set(manifest), set(expected_artifacts))
            for artifact_name, filename in expected_artifacts.items():
                content = (data_dir / filename).read_bytes()
                mirror_path = mirror_dir / filename
                self.assertEqual(manifest[artifact_name]["sha256"], hashlib.sha256(content).hexdigest())
                self.assertEqual(manifest[artifact_name]["byte_size"], len(content))
                self.assertTrue(mirror_path.is_file())
                self.assertEqual(mirror_path.read_bytes(), content)
            self.assertEqual(
                artifacts["graph"]["generation"]["run_id"],
                artifacts["summary"]["derived_from_graph_run_id"],
            )

    def test_writer_staging_failure_preserves_existing_json_files(self) -> None:
        import src.output.risk_intel_json as risk_intel_json
        from src.output.json_writer import write_json_file as real_write_json_file

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "web").mkdir()
            risk_intel_json.write_risk_intel_outputs(
                output_root=root / "output",
                project_root=root,
                run_date=date(2026, 5, 19),
                policy_payload=policy_payload(),
                search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
                watchlist=nvda_watchlist(),
                portfolio_summary=None,
                sector_payload=ai_sector_payload(),
            )
            data_dir = root / "output" / "data"
            filenames = [
                "risk_intel_graph.json",
                "risk_intel_summary.json",
                "risk_intel_refresh_log.json",
            ]
            original = {filename: (data_dir / filename).read_bytes() for filename in filenames}

            def flaky_write_json_file(path: Path, payload: object, *args: object, **kwargs: object) -> None:
                if path.name == "risk_intel_summary.json":
                    raise RuntimeError("simulated summary write failure")
                real_write_json_file(path, payload, *args, **kwargs)

            with patch("src.output.risk_intel_json.write_json_file", side_effect=flaky_write_json_file):
                with self.assertRaises(RuntimeError):
                    risk_intel_json.write_risk_intel_outputs(
                        output_root=root / "output",
                        project_root=root,
                        run_date=date(2026, 5, 20),
                        policy_payload=policy_payload(),
                        search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
                        watchlist=nvda_watchlist(),
                        portfolio_summary=None,
                        sector_payload=ai_sector_payload(),
                    )

            self.assertEqual({filename: (data_dir / filename).read_bytes() for filename in filenames}, original)
            self.assertEqual(_latest_sqlite_run_id(data_dir), "run:2026-05-19-risk-intel")

    def test_writer_promotion_failure_restores_existing_json_files(self) -> None:
        import src.output.risk_intel_json as risk_intel_json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "web").mkdir()
            risk_intel_json.write_risk_intel_outputs(
                output_root=root / "output",
                project_root=root,
                run_date=date(2026, 5, 19),
                policy_payload=policy_payload(),
                search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
                watchlist=nvda_watchlist(),
                portfolio_summary=None,
                sector_payload=ai_sector_payload(),
            )
            data_dir = root / "output" / "data"
            filenames = [
                "risk_intel_graph.json",
                "risk_intel_summary.json",
                "risk_intel_refresh_log.json",
            ]
            original = {filename: (data_dir / filename).read_bytes() for filename in filenames}
            real_replace = Path.replace
            promoted: list[str] = []

            def flaky_replace(source: Path, target: object) -> Path:
                target_path = Path(target)
                if source.name in filenames and target_path.parent == data_dir and target_path.name in filenames:
                    promoted.append(target_path.name)
                    if len(promoted) == 2:
                        raise PermissionError("simulated promotion failure")
                return real_replace(source, target)

            with patch.object(Path, "replace", flaky_replace):
                with self.assertRaises(PermissionError):
                    risk_intel_json.write_risk_intel_outputs(
                        output_root=root / "output",
                        project_root=root,
                        run_date=date(2026, 5, 20),
                        policy_payload=policy_payload(),
                        search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
                        watchlist=nvda_watchlist(),
                        portfolio_summary=None,
                        sector_payload=ai_sector_payload(),
                    )

            self.assertEqual({filename: (data_dir / filename).read_bytes() for filename in filenames}, original)
            self.assertEqual(_latest_sqlite_run_id(data_dir), "run:2026-05-19-risk-intel")


if __name__ == "__main__":
    unittest.main()
