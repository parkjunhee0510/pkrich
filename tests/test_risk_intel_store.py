import sqlite3
from contextlib import closing
from copy import deepcopy
from datetime import date

import pytest

from src.output.risk_intel_builder import build_risk_intel_artifacts
from src.output.risk_intel_store import (
    RISK_INTEL_DB_FILENAME,
    STORE_USER_VERSION,
    checkpoint_store,
    ensure_store,
    latest_run_id,
    load_graph_run,
    load_refresh_requests,
    record_export_manifest,
    replace_graph_run,
)
from tests.fixtures.risk_intel_fixtures import (
    ai_sector_payload,
    held_nvda_portfolio,
    nvda_watchlist,
    policy_payload,
)


EXPECTED_TABLES = {
    "risk_intel_runs",
    "risk_intel_nodes",
    "risk_intel_edges",
    "risk_intel_source_records",
    "risk_intel_domain_rules",
    "risk_intel_input_status",
    "risk_intel_alert_paths",
    "risk_intel_health_warnings",
    "risk_intel_pending_duplicate_candidates",
    "risk_intel_export_manifest",
    "risk_intel_refresh_requests",
}


def _artifacts(run_date: date = date(2026, 5, 19)) -> dict:
    return build_risk_intel_artifacts(
        run_date=run_date,
        policy_payload=policy_payload(),
        search_evidence_payload={"provider": "cache", "items": [], "run_summary": {"status_counts": {}}},
        watchlist=nvda_watchlist(),
        portfolio_summary=held_nvda_portfolio(),
        sector_payload=ai_sector_payload(),
    )


def _count_rows(db_path, table: str) -> int:
    with closing(sqlite3.connect(db_path)) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _expected_loaded_graph(artifacts: dict) -> dict:
    graph = deepcopy(artifacts["graph"])
    graph["input_status"] = sorted(graph["input_status"], key=lambda row: row["name"])
    return graph


def test_ensure_store_is_idempotent_and_creates_schema(tmp_path) -> None:
    db_path = tmp_path / RISK_INTEL_DB_FILENAME

    ensure_store(db_path)
    ensure_store(db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'risk_intel_%'"
            )
        }
        user_version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert EXPECTED_TABLES.issubset(tables)
    assert user_version == STORE_USER_VERSION


def test_replace_graph_run_roundtrips_current_graph_contract(tmp_path) -> None:
    db_path = tmp_path / RISK_INTEL_DB_FILENAME
    artifacts = _artifacts()

    replace_graph_run(db_path, artifacts)

    assert load_graph_run(db_path) == _expected_loaded_graph(artifacts)


def test_replacing_same_run_twice_does_not_duplicate_rows(tmp_path) -> None:
    db_path = tmp_path / RISK_INTEL_DB_FILENAME
    artifacts = _artifacts()
    graph = artifacts["graph"]

    replace_graph_run(db_path, artifacts)
    replace_graph_run(db_path, artifacts)

    assert _count_rows(db_path, "risk_intel_runs") == 1
    assert _count_rows(db_path, "risk_intel_nodes") == len(graph["nodes"])
    assert _count_rows(db_path, "risk_intel_edges") == len(graph["edges"])


def test_replace_graph_run_rejects_missing_edge_endpoint_without_replacing_prior_run(tmp_path) -> None:
    db_path = tmp_path / RISK_INTEL_DB_FILENAME
    artifacts = _artifacts()
    replace_graph_run(db_path, artifacts)

    invalid_artifacts = deepcopy(artifacts)
    invalid_artifacts["graph"]["edges"][0]["target_id"] = "node:missing"

    with pytest.raises(ValueError, match="edge .* target_id .* node:missing"):
        replace_graph_run(db_path, invalid_artifacts)

    assert load_graph_run(db_path) == _expected_loaded_graph(artifacts)


def test_record_export_manifest_upserts_three_artifact_rows(tmp_path) -> None:
    db_path = tmp_path / RISK_INTEL_DB_FILENAME
    artifacts = _artifacts()
    run_id = artifacts["graph"]["generation"]["run_id"]
    replace_graph_run(db_path, artifacts)
    manifest = {
        "risk_intel_graph": {
            "path": "output/data/risk_intel_graph.json",
            "sha256": "a" * 64,
            "byte_size": 100,
        },
        "risk_intel_summary": {
            "path": "output/data/risk_intel_summary.json",
            "sha256": "b" * 64,
            "byte_size": 200,
        },
        "risk_intel_refresh_log": {
            "path": "output/data/risk_intel_refresh_log.json",
            "sha256": "c" * 64,
            "byte_size": 300,
        },
    }

    record_export_manifest(db_path, run_id, manifest, exported_at="2026-05-19T00:00:00+09:00")
    record_export_manifest(db_path, run_id, manifest, exported_at="2026-05-19T00:01:00+09:00")

    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT artifact_name, exported_at FROM risk_intel_export_manifest ORDER BY artifact_name"
        ).fetchall()

    assert len(rows) == 3
    assert {row[0] for row in rows} == set(manifest)
    assert {row[1] for row in rows} == {"2026-05-19T00:01:00+09:00"}


def test_latest_run_id_returns_latest_as_of_and_generated_at(tmp_path) -> None:
    db_path = tmp_path / RISK_INTEL_DB_FILENAME
    older = _artifacts(date(2026, 5, 18))
    newer = _artifacts(date(2026, 5, 19))

    replace_graph_run(db_path, newer)
    replace_graph_run(db_path, older)

    assert latest_run_id(db_path) == newer["graph"]["generation"]["run_id"]


def test_checkpoint_store_removes_wal_and_shm_sidecars_after_writes(tmp_path) -> None:
    db_path = tmp_path / RISK_INTEL_DB_FILENAME
    replace_graph_run(db_path, _artifacts())

    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE IF NOT EXISTS risk_intel_checkpoint_probe (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO risk_intel_checkpoint_probe DEFAULT VALUES")
        conn.commit()
        assert db_path.with_name(f"{db_path.name}-wal").exists()
        assert db_path.with_name(f"{db_path.name}-shm").exists()

    checkpoint_store(db_path)

    assert db_path.exists()
    assert not db_path.with_name(f"{db_path.name}-wal").exists()
    assert not db_path.with_name(f"{db_path.name}-shm").exists()


def test_checkpoint_store_tolerates_locked_sidecars(tmp_path) -> None:
    db_path = tmp_path / RISK_INTEL_DB_FILENAME
    replace_graph_run(db_path, _artifacts())

    held_conn = sqlite3.connect(db_path)
    try:
        held_conn.execute("PRAGMA journal_mode=WAL")
        held_conn.execute("SELECT COUNT(*) FROM risk_intel_runs").fetchone()

        checkpoint_store(db_path)

        assert held_conn.execute("SELECT COUNT(*) FROM risk_intel_runs").fetchone()[0] == 1
    finally:
        held_conn.close()


def test_load_refresh_requests_returns_empty_for_missing_db(tmp_path) -> None:
    assert load_refresh_requests(tmp_path / RISK_INTEL_DB_FILENAME, "run:missing") == []


def test_load_refresh_requests_deserializes_patch_fields(tmp_path) -> None:
    db_path = tmp_path / RISK_INTEL_DB_FILENAME
    replace_graph_run(db_path, _artifacts())
    with closing(sqlite3.connect(db_path)) as conn:
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
                "refresh:1",
                "run:2026-05-19-risk-intel",
                "ticker:NVDA",
                "pending",
                '{"node_id":"ticker:NVDA"}',
                '{"valid":true}',
                "2026-05-19T00:00:00+09:00",
                "2026-05-20T00:00:00+09:00",
                None,
                "needs review",
            ),
        )
        conn.commit()

    assert load_refresh_requests(db_path, "run:2026-05-19-risk-intel") == [
        {
            "refresh_id": "refresh:1",
            "base_graph_run_id": "run:2026-05-19-risk-intel",
            "node_id": "ticker:NVDA",
            "patch_status": "pending",
            "patch_candidate": {"node_id": "ticker:NVDA"},
            "validation_result": {"valid": True},
            "requested_at": "2026-05-19T00:00:00+09:00",
            "expires_at": "2026-05-20T00:00:00+09:00",
            "applied_run_id": None,
            "review_note": "needs review",
        }
    ]
