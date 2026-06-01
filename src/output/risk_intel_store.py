"""SQLite store for Risk Intelligence graph runs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

RISK_INTEL_DB_FILENAME = "risk_intel.sqlite"
STORE_USER_VERSION = 1

_JSON_KWARGS = {"ensure_ascii": False, "sort_keys": True, "separators": (",", ":")}
_INTERNAL_WARNING_ID_PREFIX = "__risk_intel_warning__:"
_REQUIRED_INPUTS = {
    "tier1_required": [
        "output/data/policy_impact.json",
        "output/data/search_evidence.json",
        "output/data/portfolio.json",
        "output/data/watchlist.json",
        "output/data/sector_exposure.json",
    ],
    "tier1_optional": [
        "output/data/market_reaction.json",
        "output/data/macro.json",
        "output/data/performance_telemetry.json",
        "config/sectors.yaml",
        "output/data/sectors.json",
    ],
}

_SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS risk_intel_runs (
  run_id TEXT PRIMARY KEY,
  as_of TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ok', 'partial', 'degraded', 'error')),
  schema_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  scoring_config_version TEXT NOT NULL,
  confidence_config_version TEXT NOT NULL,
  source_config_version TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_risk_intel_runs_as_of ON risk_intel_runs(as_of);
CREATE INDEX IF NOT EXISTS idx_risk_intel_runs_status ON risk_intel_runs(status);

CREATE TABLE IF NOT EXISTS risk_intel_nodes (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  canonical_id TEXT NOT NULL,
  node_type TEXT NOT NULL,
  label TEXT NOT NULL,
  label_ko TEXT NOT NULL,
  summary_ko TEXT NOT NULL,
  status TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  aliases_json TEXT NOT NULL DEFAULT '[]',
  PRIMARY KEY (run_id, id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risk_intel_nodes_canonical ON risk_intel_nodes(run_id, canonical_id);
CREATE INDEX IF NOT EXISTS idx_risk_intel_nodes_type ON risk_intel_nodes(run_id, node_type);

CREATE TABLE IF NOT EXISTS risk_intel_edges (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  relationship TEXT NOT NULL,
  relationship_label_ko TEXT NOT NULL,
  evidence_type TEXT NOT NULL CHECK (evidence_type IN ('explicit', 'inferred', 'social', 'market')),
  evidence_label_ko TEXT NOT NULL,
  confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
  severity_delta REAL NOT NULL CHECK (severity_delta >= -1.0 AND severity_delta <= 1.0),
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  inference_refs_json TEXT NOT NULL DEFAULT '[]',
  explanation_ko TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (run_id, id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risk_intel_edges_source ON risk_intel_edges(run_id, source_id);
CREATE INDEX IF NOT EXISTS idx_risk_intel_edges_target ON risk_intel_edges(run_id, target_id);
CREATE INDEX IF NOT EXISTS idx_risk_intel_edges_type ON risk_intel_edges(run_id, evidence_type);
CREATE INDEX IF NOT EXISTS idx_risk_intel_edges_source_target ON risk_intel_edges(run_id, source_id, target_id);

CREATE TABLE IF NOT EXISTS risk_intel_source_records (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  source_type TEXT NOT NULL,
  trust_tier TEXT NOT NULL,
  published_at TEXT NOT NULL,
  url TEXT,
  title TEXT NOT NULL,
  title_ko TEXT NOT NULL,
  summary_ko TEXT NOT NULL,
  target_id TEXT,
  reaction_type TEXT,
  reaction_strength TEXT CHECK (
    reaction_strength IS NULL OR reaction_strength IN ('strong', 'moderate', 'weak', 'none')
  ),
  reaction_score REAL CHECK (reaction_score IS NULL OR (reaction_score >= 0.0 AND reaction_score <= 1.0)),
  metric TEXT,
  value REAL,
  PRIMARY KEY (run_id, id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risk_intel_source_records_trust
  ON risk_intel_source_records(run_id, trust_tier);
CREATE INDEX IF NOT EXISTS idx_risk_intel_source_records_type
  ON risk_intel_source_records(run_id, source_type);
CREATE INDEX IF NOT EXISTS idx_risk_intel_source_records_target
  ON risk_intel_source_records(run_id, target_id);

CREATE TABLE IF NOT EXISTS risk_intel_domain_rules (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  version TEXT NOT NULL,
  source_type TEXT NOT NULL,
  title TEXT NOT NULL,
  title_ko TEXT NOT NULL,
  rationale_ko TEXT NOT NULL,
  rule_confidence REAL NOT NULL CHECK (rule_confidence >= 0.0 AND rule_confidence <= 1.0),
  last_reviewed TEXT NOT NULL,
  PRIMARY KEY (run_id, id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risk_intel_domain_rules_reviewed
  ON risk_intel_domain_rules(run_id, last_reviewed);

CREATE TABLE IF NOT EXISTS risk_intel_input_status (
  run_id TEXT NOT NULL,
  name TEXT NOT NULL,
  path TEXT,
  tier INTEGER NOT NULL,
  required INTEGER NOT NULL CHECK (required IN (0, 1)),
  status TEXT NOT NULL CHECK (
    status IN ('present', 'missing', 'skipped_not_enabled', 'provider_error', 'cache_only', 'stale')
  ),
  record_count INTEGER NOT NULL,
  as_of TEXT,
  PRIMARY KEY (run_id, name),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risk_intel_input_status_required
  ON risk_intel_input_status(run_id, required, status);

CREATE TABLE IF NOT EXISTS risk_intel_alert_paths (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  canonical_issue_id TEXT NOT NULL,
  target_group_type TEXT NOT NULL CHECK (target_group_type IN ('sector', 'ticker')),
  target_group_id TEXT NOT NULL,
  representative_target_id TEXT NOT NULL,
  alert_level TEXT NOT NULL CHECK (alert_level IN ('observation', 'warning', 'alert')),
  alert_level_label_ko TEXT NOT NULL,
  raw_score REAL NOT NULL CHECK (raw_score >= 0.0 AND raw_score <= 1.0),
  score REAL NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
  score_kind TEXT NOT NULL CHECK (score_kind IN ('final', 'capped_final')),
  cap_value REAL CHECK (cap_value IS NULL OR (cap_value >= 0.0 AND cap_value <= 1.0)),
  score_breakdown_json TEXT NOT NULL,
  caps_applied_json TEXT NOT NULL DEFAULT '[]',
  guardrails_applied_json TEXT NOT NULL DEFAULT '[]',
  path_node_ids_json TEXT NOT NULL,
  path_edge_ids_json TEXT NOT NULL,
  affected_sector_ids_json TEXT NOT NULL DEFAULT '[]',
  affected_ticker_ids_json TEXT NOT NULL DEFAULT '[]',
  affected_ticker_details_json TEXT NOT NULL DEFAULT '[]',
  aggregation_json TEXT NOT NULL,
  evidence_counts_json TEXT NOT NULL DEFAULT '{{}}',
  top_evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  inference_refs_json TEXT NOT NULL DEFAULT '[]',
  edge_evidence_types_json TEXT NOT NULL DEFAULT '[]',
  rationale_ko TEXT NOT NULL,
  PRIMARY KEY (run_id, id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risk_intel_alert_paths_issue
  ON risk_intel_alert_paths(run_id, canonical_issue_id);
CREATE INDEX IF NOT EXISTS idx_risk_intel_alert_paths_target
  ON risk_intel_alert_paths(run_id, target_group_type, target_group_id);
CREATE INDEX IF NOT EXISTS idx_risk_intel_alert_paths_level_score
  ON risk_intel_alert_paths(run_id, alert_level, score DESC);

CREATE TABLE IF NOT EXISTS risk_intel_health_warnings (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  code TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('info', 'warning')),
  message_ko TEXT NOT NULL,
  ref_type TEXT,
  ref_id TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risk_intel_health_warnings_run
  ON risk_intel_health_warnings(run_id, code);

CREATE TABLE IF NOT EXISTS risk_intel_pending_duplicate_candidates (
  run_id TEXT NOT NULL,
  new_candidate_id TEXT NOT NULL,
  matched_canonical_id TEXT NOT NULL,
  similarity_score REAL NOT NULL CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0),
  status TEXT NOT NULL CHECK (status IN ('pending', 'merged', 'rejected', 'expired')),
  detected_at TEXT NOT NULL,
  resolved_at TEXT,
  resolved_by TEXT,
  PRIMARY KEY (run_id, new_candidate_id, matched_canonical_id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_risk_intel_duplicate_candidates_status
  ON risk_intel_pending_duplicate_candidates(run_id, status);

CREATE TABLE IF NOT EXISTS risk_intel_export_manifest (
  run_id TEXT NOT NULL,
  artifact_name TEXT NOT NULL,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  exported_at TEXT NOT NULL,
  PRIMARY KEY (run_id, artifact_name),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS risk_intel_refresh_requests (
  refresh_id TEXT PRIMARY KEY,
  base_graph_run_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  patch_status TEXT NOT NULL CHECK (patch_status IN ('pending', 'applied', 'rejected', 'expired')),
  patch_candidate_json TEXT NOT NULL,
  validation_result_json TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  applied_run_id TEXT,
  review_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_risk_intel_refresh_requests_base
  ON risk_intel_refresh_requests(base_graph_run_id, patch_status);

PRAGMA user_version = {STORE_USER_VERSION};
"""


def ensure_store(db_path: Path) -> None:
    """Create or migrate the Risk Intelligence SQLite store."""

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def replace_graph_run(db_path: Path, artifacts: dict[str, dict[str, Any]]) -> None:
    """Replace one graph run transactionally from in-memory Risk Intelligence artifacts."""

    ensure_store(db_path)
    graph = artifacts["graph"]
    _validate_edge_endpoints(graph)
    generation = graph["generation"]
    run_id = str(generation["run_id"])
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM risk_intel_runs WHERE run_id = ?", (run_id,))
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
                    run_id,
                    str(graph["as_of"]),
                    str(graph["status"]),
                    str(graph["schema_version"]),
                    str(generation["generated_at"]),
                    str(generation["scoring_config_version"]),
                    str(generation["confidence_config_version"]),
                    str(generation["source_config_version"]),
                    str(generation["generated_at"]),
                ),
            )
            _insert_nodes(conn, run_id, graph.get("nodes", []))
            _insert_edges(conn, run_id, graph.get("edges", []))
            _insert_source_records(conn, run_id, graph.get("source_records", []))
            _insert_domain_rules(conn, run_id, graph.get("domain_rules", []))
            _insert_input_status(conn, run_id, graph.get("input_status", []))
            _insert_alert_paths(conn, run_id, graph.get("alert_paths", []))
            _insert_health_warnings(conn, run_id, graph.get("health_warnings", []))
            _insert_pending_duplicate_candidates(
                conn,
                run_id,
                graph.get("pending_duplicate_candidates", []),
                as_of=str(graph["as_of"]),
            )
    finally:
        conn.close()


def latest_run_id(db_path: Path) -> str | None:
    """Return the latest graph run ID by as_of and generated_at."""

    db_path = Path(db_path)
    if not db_path.exists():
        return None
    ensure_store(db_path)
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT run_id
            FROM risk_intel_runs
            ORDER BY as_of DESC, generated_at DESC, run_id DESC
            LIMIT 1
            """
        ).fetchone()
        return str(row["run_id"]) if row else None
    finally:
        conn.close()


def load_graph_run(db_path: Path, run_id: str | None = None) -> dict[str, Any]:
    """Load a graph run as the public Risk Intelligence graph JSON shape."""

    db_path = Path(db_path)
    if not db_path.exists():
        return {}
    selected_run_id = run_id or latest_run_id(db_path)
    if selected_run_id is None:
        return {}

    ensure_store(db_path)
    conn = _connect(db_path)
    try:
        run = conn.execute(
            """
            SELECT
              run_id,
              as_of,
              status,
              schema_version,
              generated_at,
              scoring_config_version,
              confidence_config_version,
              source_config_version
            FROM risk_intel_runs
            WHERE run_id = ?
            """,
            (selected_run_id,),
        ).fetchone()
        if run is None:
            return {}

        alert_paths = _load_alert_paths(conn, selected_run_id)
        return {
            "schema_version": run["schema_version"],
            "as_of": run["as_of"],
            "status": run["status"],
            "nodes": _load_nodes(conn, selected_run_id),
            "edges": _load_edges(conn, selected_run_id),
            "alert_paths": alert_paths,
            "source_records": _load_source_records(conn, selected_run_id),
            "domain_rules": _load_domain_rules(conn, selected_run_id),
            "required_inputs": _required_inputs(),
            "input_status": _load_input_status(conn, selected_run_id),
            "pending_duplicate_candidates": _load_pending_duplicate_candidates(conn, selected_run_id),
            "health_warnings": _load_health_warnings(conn, selected_run_id),
            "summary": {"alert_path_count": len(alert_paths)},
            "generation": {
                "run_id": run["run_id"],
                "as_of": run["as_of"],
                "scoring_config_version": run["scoring_config_version"],
                "confidence_config_version": run["confidence_config_version"],
                "source_config_version": run["source_config_version"],
                "generated_at": run["generated_at"],
            },
        }
    finally:
        conn.close()


def load_refresh_requests(db_path: Path, base_graph_run_id: str) -> list[dict[str, Any]]:
    """Load manual refresh requests for a base graph run."""

    db_path = Path(db_path)
    if not db_path.exists():
        return []
    ensure_store(db_path)
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
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
            FROM risk_intel_refresh_requests
            WHERE base_graph_run_id = ?
            ORDER BY requested_at DESC, refresh_id
            """,
            (base_graph_run_id,),
        ).fetchall()
        requests: list[dict[str, Any]] = []
        for row in rows:
            item = {
                "refresh_id": row["refresh_id"],
                "base_graph_run_id": row["base_graph_run_id"],
                "node_id": row["node_id"],
                "patch_status": row["patch_status"],
                "patch_candidate": _json_load(row["patch_candidate_json"], {}),
                "validation_result": _json_load(row["validation_result_json"], {}),
                "requested_at": row["requested_at"],
                "expires_at": row["expires_at"],
                "applied_run_id": row["applied_run_id"],
                "review_note": row["review_note"],
            }
            requests.append(item)
        return requests
    finally:
        conn.close()


def record_export_manifest(
    db_path: Path,
    run_id: str,
    manifest: dict[str, dict[str, Any]],
    *,
    exported_at: str,
) -> None:
    """Upsert JSON export manifest rows for a graph run."""

    ensure_store(db_path)
    conn = _connect(db_path)
    try:
        with conn:
            for artifact_name in sorted(manifest):
                row = manifest[artifact_name]
                conn.execute(
                    """
                    INSERT INTO risk_intel_export_manifest (
                      run_id,
                      artifact_name,
                      path,
                      sha256,
                      byte_size,
                      exported_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, artifact_name) DO UPDATE SET
                      path = excluded.path,
                      sha256 = excluded.sha256,
                      byte_size = excluded.byte_size,
                      exported_at = excluded.exported_at
                    """,
                    (
                        run_id,
                        artifact_name,
                        str(row["path"]),
                        str(row["sha256"]),
                        int(row["byte_size"]),
                        exported_at,
                    ),
                )
    finally:
        conn.close()


def checkpoint_store(db_path: Path) -> None:
    """Checkpoint and remove transient WAL sidecars for a completed store write."""

    ensure_store(db_path)
    db_path = Path(db_path)
    conn = _connect(db_path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()

    for suffix in ("-wal", "-shm"):
        sidecar = db_path.with_name(f"{db_path.name}{suffix}")
        if sidecar.exists():
            try:
                sidecar.unlink()
            except PermissionError:
                pass


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _json_text(value: Any, default: Any) -> str:
    if value is None:
        value = default
    return json.dumps(value, **_JSON_KWARGS)


def _json_load(value: str | None, default: Any) -> Any:
    if value is None or value == "":
        return default
    return json.loads(value)


def _required_inputs() -> dict[str, list[str]]:
    return {
        "tier1_required": list(_REQUIRED_INPUTS["tier1_required"]),
        "tier1_optional": list(_REQUIRED_INPUTS["tier1_optional"]),
    }


def _validate_edge_endpoints(graph: dict[str, Any]) -> None:
    node_ids = {str(row.get("id")) for row in graph.get("nodes", []) if isinstance(row, dict) and row.get("id")}
    missing: list[str] = []
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        edge_id = str(edge.get("id") or "<unknown>")
        for field in ("source_id", "target_id"):
            endpoint_id = str(edge.get(field) or "")
            if endpoint_id not in node_ids:
                missing.append(f"edge {edge_id} {field} references missing node {endpoint_id or '<empty>'}")
    if missing:
        raise ValueError("Risk Intelligence graph has unresolved edge endpoints: " + "; ".join(missing))


def _insert_nodes(conn: sqlite3.Connection, run_id: str, rows: Iterable[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO risk_intel_nodes (
          run_id,
          id,
          canonical_id,
          node_type,
          label,
          label_ko,
          summary_ko,
          status,
          first_seen,
          last_seen,
          aliases_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                run_id,
                str(row["id"]),
                str(row["canonical_id"]),
                str(row["node_type"]),
                str(row["label"]),
                str(row["label_ko"]),
                str(row["summary_ko"]),
                str(row["status"]),
                str(row["first_seen"]),
                str(row["last_seen"]),
                _json_text(row.get("aliases"), []),
            )
            for row in rows
        ),
    )


def _insert_edges(conn: sqlite3.Connection, run_id: str, rows: Iterable[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO risk_intel_edges (
          run_id,
          id,
          source_id,
          target_id,
          relationship,
          relationship_label_ko,
          evidence_type,
          evidence_label_ko,
          confidence,
          severity_delta,
          evidence_refs_json,
          inference_refs_json,
          explanation_ko,
          created_at,
          updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                run_id,
                str(row["id"]),
                str(row["source_id"]),
                str(row["target_id"]),
                str(row["relationship"]),
                str(row["relationship_label_ko"]),
                str(row["evidence_type"]),
                str(row["evidence_label_ko"]),
                float(row["confidence"]),
                float(row["severity_delta"]),
                _json_text(row.get("evidence_refs"), []),
                _json_text(row.get("inference_refs"), []),
                str(row["explanation_ko"]),
                str(row["created_at"]),
                str(row["updated_at"]),
            )
            for row in rows
        ),
    )


def _insert_source_records(conn: sqlite3.Connection, run_id: str, rows: Iterable[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO risk_intel_source_records (
          run_id,
          id,
          source_type,
          trust_tier,
          published_at,
          url,
          title,
          title_ko,
          summary_ko,
          target_id,
          reaction_type,
          reaction_strength,
          reaction_score,
          metric,
          value
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                run_id,
                str(row["id"]),
                str(row["source_type"]),
                str(row["trust_tier"]),
                str(row["published_at"]),
                row.get("url"),
                str(row["title"]),
                str(row["title_ko"]),
                str(row["summary_ko"]),
                row.get("target_id"),
                row.get("reaction_type"),
                row.get("reaction_strength"),
                _optional_float(row.get("reaction_score")),
                row.get("metric"),
                _optional_float(row.get("value")),
            )
            for row in rows
        ),
    )


def _insert_domain_rules(conn: sqlite3.Connection, run_id: str, rows: Iterable[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO risk_intel_domain_rules (
          run_id,
          id,
          version,
          source_type,
          title,
          title_ko,
          rationale_ko,
          rule_confidence,
          last_reviewed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                run_id,
                str(row["id"]),
                str(row["version"]),
                str(row["source_type"]),
                str(row["title"]),
                str(row["title_ko"]),
                str(row["rationale_ko"]),
                float(row["rule_confidence"]),
                str(row["last_reviewed"]),
            )
            for row in rows
        ),
    )


def _insert_input_status(conn: sqlite3.Connection, run_id: str, rows: Iterable[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO risk_intel_input_status (
          run_id,
          name,
          path,
          tier,
          required,
          status,
          record_count,
          as_of
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                run_id,
                str(row["name"]),
                row.get("path"),
                int(row["tier"]),
                1 if row.get("required") else 0,
                str(row["status"]),
                int(row["record_count"]),
                row.get("as_of"),
            )
            for row in rows
        ),
    )


def _insert_alert_paths(conn: sqlite3.Connection, run_id: str, rows: Iterable[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO risk_intel_alert_paths (
          run_id,
          id,
          canonical_issue_id,
          target_group_type,
          target_group_id,
          representative_target_id,
          alert_level,
          alert_level_label_ko,
          raw_score,
          score,
          score_kind,
          cap_value,
          score_breakdown_json,
          caps_applied_json,
          guardrails_applied_json,
          path_node_ids_json,
          path_edge_ids_json,
          affected_sector_ids_json,
          affected_ticker_ids_json,
          affected_ticker_details_json,
          aggregation_json,
          evidence_counts_json,
          top_evidence_refs_json,
          inference_refs_json,
          edge_evidence_types_json,
          rationale_ko
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                run_id,
                str(row["id"]),
                str(row["canonical_issue_id"]),
                str(row["target_group_type"]),
                str(row["target_group_id"]),
                str(row["representative_target_id"]),
                str(row["alert_level"]),
                str(row["alert_level_label_ko"]),
                float(row["raw_score"]),
                float(row["score"]),
                str(row["score_kind"]),
                _optional_float(row.get("cap_value")),
                _json_text(row.get("score_breakdown"), {}),
                _json_text(row.get("caps_applied"), []),
                _json_text(row.get("guardrails_applied"), []),
                _json_text(row.get("path_node_ids"), []),
                _json_text(row.get("path_edge_ids"), []),
                _json_text(row.get("affected_sector_ids"), []),
                _json_text(row.get("affected_ticker_ids"), []),
                _json_text(row.get("affected_ticker_details"), []),
                _json_text(row.get("aggregation"), {}),
                _json_text(row.get("evidence_counts"), {}),
                _json_text(row.get("top_evidence_refs"), []),
                _json_text(row.get("inference_refs"), []),
                _json_text(row.get("edge_evidence_types"), []),
                str(row["rationale_ko"]),
            )
            for row in rows
        ),
    )


def _insert_health_warnings(conn: sqlite3.Connection, run_id: str, rows: Iterable[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO risk_intel_health_warnings (
          run_id,
          id,
          code,
          severity,
          message_ko,
          ref_type,
          ref_id,
          created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                run_id,
                str(row.get("id") or f"{_INTERNAL_WARNING_ID_PREFIX}{index:04d}"),
                str(row["code"]),
                str(row["severity"]),
                str(row["message_ko"]),
                row.get("ref_type"),
                row.get("ref_id"),
                str(row["created_at"]),
            )
            for index, row in enumerate(rows, start=1)
        ),
    )


def _insert_pending_duplicate_candidates(
    conn: sqlite3.Connection,
    run_id: str,
    rows: Iterable[dict[str, Any]],
    *,
    as_of: str,
) -> None:
    conn.executemany(
        """
        INSERT INTO risk_intel_pending_duplicate_candidates (
          run_id,
          new_candidate_id,
          matched_canonical_id,
          similarity_score,
          status,
          detected_at,
          resolved_at,
          resolved_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                run_id,
                str(row["new_candidate_id"]),
                str(row["matched_canonical_id"]),
                float(row["similarity_score"]),
                str(row["status"]),
                str(row.get("detected_at") or as_of),
                row.get("resolved_at"),
                row.get("resolved_by"),
            )
            for row in rows
        ),
    )


def _load_nodes(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          id,
          canonical_id,
          aliases_json,
          node_type,
          label,
          label_ko,
          summary_ko,
          status,
          first_seen,
          last_seen
        FROM risk_intel_nodes
        WHERE run_id = ?
        ORDER BY id
        """,
        (run_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "canonical_id": row["canonical_id"],
            "aliases": _json_load(row["aliases_json"], []),
            "node_type": row["node_type"],
            "label": row["label"],
            "label_ko": row["label_ko"],
            "summary_ko": row["summary_ko"],
            "status": row["status"],
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
        }
        for row in rows
    ]


def _load_edges(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          id,
          source_id,
          target_id,
          relationship,
          relationship_label_ko,
          evidence_type,
          evidence_label_ko,
          confidence,
          severity_delta,
          evidence_refs_json,
          inference_refs_json,
          explanation_ko,
          created_at,
          updated_at
        FROM risk_intel_edges
        WHERE run_id = ?
        ORDER BY id
        """,
        (run_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "source_id": row["source_id"],
            "target_id": row["target_id"],
            "relationship": row["relationship"],
            "relationship_label_ko": row["relationship_label_ko"],
            "evidence_type": row["evidence_type"],
            "evidence_label_ko": row["evidence_label_ko"],
            "confidence": row["confidence"],
            "severity_delta": row["severity_delta"],
            "evidence_refs": _json_load(row["evidence_refs_json"], []),
            "inference_refs": _json_load(row["inference_refs_json"], []),
            "explanation_ko": row["explanation_ko"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def _load_source_records(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          id,
          source_type,
          trust_tier,
          published_at,
          url,
          title,
          title_ko,
          summary_ko,
          target_id,
          reaction_type,
          reaction_strength,
          reaction_score,
          metric,
          value
        FROM risk_intel_source_records
        WHERE run_id = ?
        ORDER BY id
        """,
        (run_id,),
    ).fetchall()
    records: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "id": row["id"],
            "source_type": row["source_type"],
            "title": row["title"],
            "title_ko": row["title_ko"],
            "url": row["url"],
            "published_at": row["published_at"],
            "trust_tier": row["trust_tier"],
            "summary_ko": row["summary_ko"],
        }
        _add_optional(item, row, "target_id", "reaction_type", "reaction_strength", "reaction_score", "metric", "value")
        records.append(item)
    return records


def _load_domain_rules(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          id,
          version,
          source_type,
          title,
          title_ko,
          rationale_ko,
          rule_confidence,
          last_reviewed
        FROM risk_intel_domain_rules
        WHERE run_id = ?
        ORDER BY id
        """,
        (run_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "version": row["version"],
            "source_type": row["source_type"],
            "title": row["title"],
            "title_ko": row["title_ko"],
            "rationale_ko": row["rationale_ko"],
            "rule_confidence": row["rule_confidence"],
            "last_reviewed": row["last_reviewed"],
        }
        for row in rows
    ]


def _load_input_status(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          name,
          path,
          tier,
          required,
          status,
          record_count,
          as_of
        FROM risk_intel_input_status
        WHERE run_id = ?
        ORDER BY name
        """,
        (run_id,),
    ).fetchall()
    statuses: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "name": row["name"],
            "tier": row["tier"],
            "required": bool(row["required"]),
            "status": row["status"],
            "record_count": row["record_count"],
        }
        if row["path"] is not None:
            item["path"] = row["path"]
        if row["as_of"] is not None:
            item["as_of"] = row["as_of"]
        statuses.append(item)
    return statuses


def _load_alert_paths(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          id,
          canonical_issue_id,
          target_group_type,
          target_group_id,
          representative_target_id,
          alert_level,
          alert_level_label_ko,
          raw_score,
          score,
          score_kind,
          cap_value,
          score_breakdown_json,
          caps_applied_json,
          guardrails_applied_json,
          path_node_ids_json,
          path_edge_ids_json,
          affected_sector_ids_json,
          affected_ticker_ids_json,
          affected_ticker_details_json,
          aggregation_json,
          evidence_counts_json,
          top_evidence_refs_json,
          inference_refs_json,
          edge_evidence_types_json,
          rationale_ko
        FROM risk_intel_alert_paths
        WHERE run_id = ?
        ORDER BY
          CASE alert_level WHEN 'alert' THEN 0 WHEN 'warning' THEN 1 WHEN 'observation' THEN 2 ELSE 99 END,
          score DESC,
          id
        """,
        (run_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "canonical_issue_id": row["canonical_issue_id"],
            "target_group_type": row["target_group_type"],
            "target_group_id": row["target_group_id"],
            "alert_level": row["alert_level"],
            "alert_level_label_ko": row["alert_level_label_ko"],
            "path_node_ids": _json_load(row["path_node_ids_json"], []),
            "path_edge_ids": _json_load(row["path_edge_ids_json"], []),
            "edge_evidence_types": _json_load(row["edge_evidence_types_json"], []),
            "inference_refs": _json_load(row["inference_refs_json"], []),
            "affected_sector_ids": _json_load(row["affected_sector_ids_json"], []),
            "affected_ticker_ids": _json_load(row["affected_ticker_ids_json"], []),
            "affected_ticker_details": _json_load(row["affected_ticker_details_json"], []),
            "representative_target_id": row["representative_target_id"],
            "raw_score": row["raw_score"],
            "score": row["score"],
            "score_kind": row["score_kind"],
            "cap_value": row["cap_value"],
            "score_breakdown": _json_load(row["score_breakdown_json"], {}),
            "caps_applied": _json_load(row["caps_applied_json"], []),
            "guardrails_applied": _json_load(row["guardrails_applied_json"], []),
            "aggregation": _json_load(row["aggregation_json"], {}),
            "evidence_counts": _json_load(row["evidence_counts_json"], {}),
            "top_evidence_refs": _json_load(row["top_evidence_refs_json"], []),
            "rationale_ko": row["rationale_ko"],
        }
        for row in rows
    ]


def _load_health_warnings(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          id,
          code,
          severity,
          message_ko,
          ref_type,
          ref_id,
          created_at
        FROM risk_intel_health_warnings
        WHERE run_id = ?
        ORDER BY id
        """,
        (run_id,),
    ).fetchall()
    warnings: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "code": row["code"],
            "severity": row["severity"],
            "message_ko": row["message_ko"],
            "created_at": row["created_at"],
        }
        if not str(row["id"]).startswith(_INTERNAL_WARNING_ID_PREFIX):
            item["id"] = row["id"]
        _add_optional(item, row, "ref_type", "ref_id")
        warnings.append(item)
    return warnings


def _load_pending_duplicate_candidates(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          new_candidate_id,
          matched_canonical_id,
          similarity_score,
          status,
          detected_at,
          resolved_at,
          resolved_by
        FROM risk_intel_pending_duplicate_candidates
        WHERE run_id = ?
        ORDER BY new_candidate_id, matched_canonical_id
        """,
        (run_id,),
    ).fetchall()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "new_candidate_id": row["new_candidate_id"],
            "matched_canonical_id": row["matched_canonical_id"],
            "similarity_score": row["similarity_score"],
            "status": row["status"],
            "detected_at": row["detected_at"],
        }
        _add_optional(item, row, "resolved_at", "resolved_by")
        candidates.append(item)
    return candidates


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _add_optional(item: dict[str, Any], row: sqlite3.Row, *keys: str) -> None:
    for key in keys:
        if row[key] is not None:
            item[key] = row[key]
