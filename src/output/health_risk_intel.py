"""Health checks for risk intelligence graph artifacts."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import date
from pathlib import Path
from typing import Callable, Iterable

from src.output.health_common import OutputHealthIssue, _is_probability, _is_string_list, _load_json_object
from src.output.risk_intel_config import (
    ALERT_LEVELS,
    ARTIFACT_STATUSES,
    CONFIDENCE_BANDS,
    DUPLICATE_STATUSES,
    INPUT_STATUSES,
    RISK_INTEL_SCHEMA_VERSION,
)
from src.output.risk_intel_scoring import raw_score
from src.output.risk_intel_store import RISK_INTEL_DB_FILENAME


def _validate_risk_intel_artifacts(root: Path, *, web_data_dir: Path | None = None) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    issues: list[OutputHealthIssue] = []
    graph_path = root / "risk_intel_graph.json"
    summary_path = root / "risk_intel_summary.json"
    refresh_path = root / "risk_intel_refresh_log.json"
    graph = _load_json_object(graph_path) if graph_path.exists() else {}
    summary = _load_json_object(summary_path) if summary_path.exists() else {}
    refresh = _load_json_object(refresh_path) if refresh_path.exists() else {}
    if graph_path.exists():
        issues.extend(_validate_graph(graph_path, graph))
    if summary_path.exists():
        issues.extend(_validate_summary(summary_path, summary, graph))
    if refresh_path.exists():
        issues.extend(_validate_refresh_log(refresh_path, refresh))
    if graph_path.exists():
        issues.extend(_validate_sqlite_store(root, graph, summary, refresh, web_data_dir=web_data_dir))
    return tuple(issues)


def _issue(path: Path, code: str, detail: str) -> OutputHealthIssue:
    return OutputHealthIssue(code, str(path), detail)


def _validate_graph(path: Path, graph: dict) -> list[OutputHealthIssue]:
    issues: list[OutputHealthIssue] = []
    required_roots = {
        "schema_version",
        "as_of",
        "status",
        "nodes",
        "edges",
        "alert_paths",
        "source_records",
        "domain_rules",
        "required_inputs",
        "input_status",
        "pending_duplicate_candidates",
        "health_warnings",
        "generation",
    }
    if not required_roots.issubset(graph):
        return [_issue(path, "invalid_risk_intel_graph", "missing required root fields")]

    if graph.get("schema_version") != RISK_INTEL_SCHEMA_VERSION:
        issues.append(_issue(path, "invalid_risk_intel_graph", "schema_version must be 1.0.0"))
    if graph.get("status") not in ARTIFACT_STATUSES:
        issues.append(_issue(path, "invalid_risk_intel_graph", "status is not a known artifact status"))

    for key in (
        "nodes",
        "edges",
        "alert_paths",
        "source_records",
        "domain_rules",
        "input_status",
        "pending_duplicate_candidates",
        "health_warnings",
    ):
        if not isinstance(graph.get(key), list):
            issues.append(_issue(path, "invalid_risk_intel_graph", f"{key} must be an array"))

    source_ids = {record.get("id") for record in graph.get("source_records", []) if isinstance(record, dict)}
    rule_ids = {rule.get("id") for rule in graph.get("domain_rules", []) if isinstance(rule, dict)}
    stale_rule_ids = {
        str(rule.get("id"))
        for rule in graph.get("domain_rules", [])
        if isinstance(rule, dict) and _is_stale_rule(rule, str(graph.get("as_of", "")))
    }

    for row in graph.get("input_status", []):
        if not isinstance(row, dict) or row.get("status") not in INPUT_STATUSES:
            issues.append(_issue(path, "invalid_risk_intel_graph", "input_status rows must use known statuses"))

    for candidate in graph.get("pending_duplicate_candidates", []):
        if not isinstance(candidate, dict):
            issues.append(_issue(path, "invalid_risk_intel_graph", "pending duplicate candidates must be objects"))
        elif candidate.get("status") not in DUPLICATE_STATUSES:
            issues.append(_issue(path, "invalid_risk_intel_graph", "pending duplicate candidate has unknown status"))

    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            issues.append(_issue(path, "invalid_risk_intel_graph", "edge rows must be objects"))
            continue
        if not _is_probability(edge.get("confidence")):
            issues.append(_issue(path, "invalid_risk_intel_graph", "edge confidence must be 0..1"))
        elif edge.get("evidence_type") in CONFIDENCE_BANDS:
            confidence = float(edge["confidence"])
            bands = CONFIDENCE_BANDS[str(edge["evidence_type"])].values()
            if not any(low <= confidence <= high for low, high in bands):
                issues.append(_issue(path, "invalid_risk_intel_graph", "edge confidence must match configured band"))

        severity = edge.get("severity_delta")
        if isinstance(severity, bool) or not isinstance(severity, (int, float)) or not -1.0 <= float(severity) <= 1.0:
            issues.append(_issue(path, "invalid_risk_intel_graph", "edge severity_delta must be -1..1"))
        if not str(edge.get("explanation_ko", "")).strip():
            issues.append(_issue(path, "invalid_risk_intel_graph", "edge explanation_ko is required"))

        evidence_refs = edge.get("evidence_refs")
        if not _is_string_list(evidence_refs) or any(ref not in source_ids for ref in evidence_refs):
            issues.append(_issue(path, "invalid_risk_intel_graph", "edge evidence_refs must reference source_records"))

        if edge.get("evidence_type") == "inferred":
            inference_refs = edge.get("inference_refs")
            if not _is_string_list(inference_refs) or not inference_refs:
                issues.append(_issue(path, "invalid_risk_intel_graph", "inferred edge requires inference_refs"))
            elif any(ref not in rule_ids for ref in inference_refs):
                issues.append(_issue(path, "invalid_risk_intel_graph", "inference_refs must reference domain_rules"))

    for path_row in graph.get("alert_paths", []):
        issues.extend(_validate_alert_path(path, path_row))

    promoted_stale_refs = {
        ref
        for row in graph.get("alert_paths", [])
        if isinstance(row, dict) and row.get("alert_level") != "observation"
        for ref in row.get("inference_refs", [])
        if ref in stale_rule_ids
    }
    if promoted_stale_refs and graph.get("status") != "degraded":
        issues.append(_issue(path, "invalid_risk_intel_graph", "promoted stale domain rule requires degraded status"))

    warning_refs = {
        str(row.get("ref_id"))
        for row in graph.get("health_warnings", [])
        if isinstance(row, dict) and row.get("code") in {"stale_domain_rule", "stale_domain_rule_promoted"}
    }
    if stale_rule_ids and not stale_rule_ids.issubset(warning_refs):
        issues.append(_issue(path, "invalid_risk_intel_graph", "stale domain rules must be listed in health_warnings"))

    return issues


def _is_stale_rule(rule: dict, as_of: str) -> bool:
    try:
        reviewed = date.fromisoformat(str(rule.get("last_reviewed", ""))[:10])
        current = date.fromisoformat(as_of[:10])
    except ValueError:
        return True
    return (current - reviewed).days > 365


def _validate_alert_path(path: Path, row: object) -> list[OutputHealthIssue]:
    if not isinstance(row, dict):
        return [_issue(path, "invalid_risk_intel_graph", "alert path rows must be objects")]

    issues: list[OutputHealthIssue] = []
    for key in (
        "canonical_issue_id",
        "target_group_type",
        "target_group_id",
        "raw_score",
        "score",
        "score_kind",
        "cap_value",
        "score_breakdown",
    ):
        if key not in row:
            issues.append(_issue(path, "invalid_risk_intel_graph", f"alert path missing {key}"))

    if row.get("alert_level") not in ALERT_LEVELS:
        issues.append(_issue(path, "invalid_risk_intel_graph", "alert path has unknown alert_level"))

    raw_score_value = _alert_path_number(path, row, "raw_score", issues) if "raw_score" in row else None
    score_value = _alert_path_number(path, row, "score", issues) if "score" in row else None
    cap_value = _alert_path_number(path, row, "cap_value", issues, allow_none=True) if "cap_value" in row else None

    breakdown = row.get("score_breakdown", {})
    if isinstance(breakdown, dict) and raw_score_value is not None:
        try:
            computed_raw = raw_score({k: float(v) for k, v in breakdown.items()})
        except (TypeError, ValueError):
            issues.append(_issue(path, "invalid_risk_intel_graph", "score_breakdown values must be numeric"))
        else:
            if abs(computed_raw - raw_score_value) > 0.01:
                issues.append(
                    _issue(path, "invalid_risk_intel_graph", "score_breakdown weighted sum must match raw_score")
                )

    if row.get("caps_applied"):
        if cap_value is not None and score_value is not None and score_value > cap_value:
            issues.append(_issue(path, "invalid_risk_intel_graph", "capped score must be at or below cap_value"))
        elif cap_value is None and row.get("cap_value") is None:
            issues.append(_issue(path, "invalid_risk_intel_graph", "capped score must be at or below cap_value"))
    elif raw_score_value is not None and score_value is not None and abs(score_value - raw_score_value) > 0.01:
        issues.append(_issue(path, "invalid_risk_intel_graph", "uncapped score must match raw_score"))

    if row.get("alert_level") == "alert" and not row.get("top_evidence_refs"):
        issues.append(_issue(path, "invalid_risk_intel_graph", "alert path requires top_evidence_refs"))
    return issues


def _alert_path_number(
    path: Path,
    row: dict,
    field: str,
    issues: list[OutputHealthIssue],
    *,
    allow_none: bool = False,
) -> float | None:
    value = row.get(field)
    if value is None and allow_none:
        return None
    if isinstance(value, bool):
        issues.append(_issue(path, "invalid_risk_intel_graph", f"alert path {field} must be numeric"))
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        issues.append(_issue(path, "invalid_risk_intel_graph", f"alert path {field} must be numeric"))
        return None
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        issues.append(
            _issue(path, "invalid_risk_intel_graph", f"alert path {field} must be a finite number between 0 and 1")
        )
        return None
    return number


def _validate_summary(path: Path, summary: dict, graph: dict) -> list[OutputHealthIssue]:
    issues: list[OutputHealthIssue] = []
    if summary.get("derived_from_graph_run_id") != graph.get("generation", {}).get("run_id"):
        issues.append(
            _issue(
                path,
                "risk_intel_run_id_mismatch",
                "summary derived_from_graph_run_id must match graph generation.run_id",
            )
        )
    for card in summary.get("cards", []):
        if (
            not isinstance(card, dict)
            or not str(card.get("title_ko", "")).strip()
            or not str(card.get("summary_ko", "")).strip()
        ):
            issues.append(_issue(path, "invalid_risk_intel_summary", "cards require Korean title_ko and summary_ko"))
    return issues


def _validate_refresh_log(path: Path, refresh: dict) -> list[OutputHealthIssue]:
    required = {
        "schema_version",
        "as_of",
        "status",
        "daily_limit",
        "used_today",
        "runs",
        "latest",
        "counters",
        "generation",
        "reset_timezone",
        "reset_at_local",
    }
    if refresh and not required.issubset(refresh):
        return [_issue(path, "invalid_risk_intel_refresh_log", "missing refresh log root fields")]
    return []


def _validate_sqlite_store(
    root: Path,
    graph: dict,
    summary: dict,
    refresh: dict,
    *,
    web_data_dir: Path | None = None,
) -> list[OutputHealthIssue]:
    issues: list[OutputHealthIssue] = []
    db_path = root / RISK_INTEL_DB_FILENAME
    mirror_roots = [web_data_dir] if web_data_dir is not None else []
    default_mirror_root = root.parent.parent / "web" / "public" / "output" / "data"
    mirror_roots.append(default_mirror_root)
    seen_mirrors: set[Path] = set()
    for mirror_root in mirror_roots:
        if mirror_root is None:
            continue
        for filename in (
            RISK_INTEL_DB_FILENAME,
            f"{RISK_INTEL_DB_FILENAME}-wal",
            f"{RISK_INTEL_DB_FILENAME}-shm",
        ):
            mirrored = mirror_root / filename
            if mirrored in seen_mirrors:
                continue
            seen_mirrors.add(mirrored)
            if mirrored.exists():
                issues.append(
                    _issue(mirrored, "risk_intel_sqlite_mirrored", "risk intel sqlite files must not be mirrored")
                )

    if not db_path.exists():
        issues.append(_issue(db_path, "risk_intel_sqlite_missing", "risk intel sqlite store is required"))
        return issues

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        issues.append(_issue(db_path, "risk_intel_sqlite_invalid", f"cannot open sqlite store: {exc}"))
        return issues

    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            issues.append(_issue(db_path, "risk_intel_sqlite_invalid", "sqlite integrity_check failed"))

        expected_tables = {
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
        actual_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'risk_intel_%'"
            )
        }
        missing_tables = expected_tables - actual_tables
        if missing_tables:
            issues.append(_issue(db_path, "risk_intel_sqlite_invalid", f"missing tables: {sorted(missing_tables)}"))
            return issues

        run_id = str(graph.get("generation", {}).get("run_id", ""))
        if not run_id:
            return issues

        latest = conn.execute(
            """
            SELECT run_id
            FROM risk_intel_runs
            ORDER BY as_of DESC, generated_at DESC, run_id DESC
            LIMIT 1
            """
        ).fetchone()
        if latest is not None and str(latest["run_id"]) != run_id:
            issues.append(
                _issue(
                    db_path,
                    "risk_intel_sqlite_run_mismatch",
                    "latest sqlite run does not match public graph run",
                )
            )

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
            (run_id,),
        ).fetchone()
        if run is None:
            issues.append(_issue(db_path, "risk_intel_sqlite_run_missing", f"missing run {run_id}"))
            return issues

        issues.extend(_validate_sqlite_run_metadata(db_path, run, graph))

        if summary and summary.get("derived_from_graph_run_id") != run_id:
            issues.append(_issue(db_path, "risk_intel_sqlite_run_mismatch", "summary run_id does not match sqlite run"))
        if refresh and refresh.get("generation", {}).get("run_id") != run_id:
            issues.append(
                _issue(db_path, "risk_intel_sqlite_run_mismatch", "refresh log run_id does not match sqlite run")
            )

        count_checks = {
            "nodes": ("risk_intel_nodes", graph.get("nodes", [])),
            "edges": ("risk_intel_edges", graph.get("edges", [])),
            "source_records": ("risk_intel_source_records", graph.get("source_records", [])),
            "domain_rules": ("risk_intel_domain_rules", graph.get("domain_rules", [])),
            "input_status": ("risk_intel_input_status", graph.get("input_status", [])),
            "pending_duplicate_candidates": (
                "risk_intel_pending_duplicate_candidates",
                graph.get("pending_duplicate_candidates", []),
            ),
            "health_warnings": ("risk_intel_health_warnings", graph.get("health_warnings", [])),
            "alert_paths": ("risk_intel_alert_paths", graph.get("alert_paths", [])),
        }
        for label, (table, json_rows) in count_checks.items():
            db_count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE run_id = ?", (run_id,)).fetchone()[0]
            json_count = len(json_rows) if isinstance(json_rows, list) else 0
            if db_count != json_count:
                issues.append(_issue(db_path, "risk_intel_sqlite_count_mismatch", f"{label} count differs from JSON"))

        json_issues, sqlite_json = _validate_sqlite_json_columns(db_path, conn, run_id)
        issues.extend(json_issues)
        issues.extend(_validate_sqlite_references(db_path, conn, run_id, sqlite_json))
        issues.extend(_validate_manifest(db_path, conn, run_id, root))
    except sqlite3.Error as exc:
        issues.append(_issue(db_path, "risk_intel_sqlite_invalid", f"sqlite validation failed: {exc}"))
    finally:
        conn.close()

    return issues


def _validate_sqlite_run_metadata(
    db_path: Path,
    run: sqlite3.Row,
    graph: dict,
) -> list[OutputHealthIssue]:
    issues: list[OutputHealthIssue] = []
    generation = graph.get("generation", {}) if isinstance(graph.get("generation"), dict) else {}
    expected = {
        "as_of": str(graph.get("as_of", "")),
        "status": str(graph.get("status", "")),
        "schema_version": str(graph.get("schema_version", "")),
        "generated_at": str(generation.get("generated_at", "")),
        "scoring_config_version": str(generation.get("scoring_config_version", "")),
        "confidence_config_version": str(generation.get("confidence_config_version", "")),
        "source_config_version": str(generation.get("source_config_version", "")),
    }
    for column, expected_value in expected.items():
        if str(run[column]) != expected_value:
            issues.append(
                _issue(
                    db_path,
                    "risk_intel_sqlite_run_mismatch",
                    f"sqlite run {column} does not match public graph",
                )
            )
    return issues


def _validate_sqlite_json_columns(
    db_path: Path,
    conn: sqlite3.Connection,
    run_id: str,
) -> tuple[list[OutputHealthIssue], dict[tuple[str, str, str], object]]:
    issues: list[OutputHealthIssue] = []
    parsed: dict[tuple[str, str, str], object] = {}

    for row in conn.execute("SELECT id, aliases_json FROM risk_intel_nodes WHERE run_id = ?", (run_id,)):
        _parse_sqlite_json_column(
            db_path,
            issues,
            parsed,
            "risk_intel_nodes",
            row["id"],
            "aliases_json",
            row["aliases_json"],
            _is_list,
            "list",
        )

    for row in conn.execute(
        "SELECT id, evidence_refs_json, inference_refs_json FROM risk_intel_edges WHERE run_id = ?",
        (run_id,),
    ):
        _parse_sqlite_json_column(
            db_path,
            issues,
            parsed,
            "risk_intel_edges",
            row["id"],
            "evidence_refs_json",
            row["evidence_refs_json"],
            _is_str_list,
            "list[str]",
        )
        _parse_sqlite_json_column(
            db_path,
            issues,
            parsed,
            "risk_intel_edges",
            row["id"],
            "inference_refs_json",
            row["inference_refs_json"],
            _is_str_list,
            "list[str]",
        )

    alert_json_columns: tuple[tuple[str, object, str], ...] = (
        ("score_breakdown_json", _is_dict, "dict"),
        ("caps_applied_json", _is_str_list, "list[str]"),
        ("guardrails_applied_json", _is_str_list, "list[str]"),
        ("path_node_ids_json", _is_str_list, "list[str]"),
        ("path_edge_ids_json", _is_str_list, "list[str]"),
        ("affected_sector_ids_json", _is_str_list, "list[str]"),
        ("affected_ticker_ids_json", _is_str_list, "list[str]"),
        ("affected_ticker_details_json", _is_list, "list"),
        ("aggregation_json", _is_dict, "dict"),
        ("evidence_counts_json", _is_dict, "dict"),
        ("top_evidence_refs_json", _is_str_list, "list[str]"),
        ("inference_refs_json", _is_str_list, "list[str]"),
        ("edge_evidence_types_json", _is_str_list, "list[str]"),
    )
    columns = ", ".join(["id", *(column for column, _, _ in alert_json_columns)])
    for row in conn.execute(f"SELECT {columns} FROM risk_intel_alert_paths WHERE run_id = ?", (run_id,)):
        for column, validator, expected_shape in alert_json_columns:
            _parse_sqlite_json_column(
                db_path,
                issues,
                parsed,
                "risk_intel_alert_paths",
                row["id"],
                column,
                row[column],
                validator,
                expected_shape,
            )

    for row in conn.execute(
        """
        SELECT refresh_id, patch_candidate_json, validation_result_json
        FROM risk_intel_refresh_requests
        WHERE base_graph_run_id = ?
        """,
        (run_id,),
    ):
        _parse_sqlite_json_column(
            db_path,
            issues,
            parsed,
            "risk_intel_refresh_requests",
            row["refresh_id"],
            "patch_candidate_json",
            row["patch_candidate_json"],
            _is_dict,
            "dict",
        )
        _parse_sqlite_json_column(
            db_path,
            issues,
            parsed,
            "risk_intel_refresh_requests",
            row["refresh_id"],
            "validation_result_json",
            row["validation_result_json"],
            _is_dict,
            "dict",
        )

    return issues, parsed


def _parse_sqlite_json_column(
    db_path: Path,
    issues: list[OutputHealthIssue],
    parsed: dict[tuple[str, str, str], object],
    table: str,
    row_id: str,
    column: str,
    raw_value: str,
    validator: Callable[[object], bool],
    expected_shape: str,
) -> None:
    try:
        value = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        issues.append(_issue(db_path, "risk_intel_sqlite_json_invalid", f"{table} {row_id} {column} invalid JSON"))
        return
    if not validator(value):
        issues.append(
            _issue(
                db_path,
                "risk_intel_sqlite_json_invalid",
                f"{table} {row_id} {column} must be {expected_shape}",
            )
        )
        return
    parsed[(table, str(row_id), column)] = value


def _is_list(value: object) -> bool:
    return isinstance(value, list)


def _is_dict(value: object) -> bool:
    return isinstance(value, dict)


def _is_str_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _sqlite_json_list(
    parsed: dict[tuple[str, str, str], object],
    table: str,
    row_id: str,
    column: str,
) -> list[str]:
    value = parsed.get((table, str(row_id), column))
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return []


def _validate_sqlite_references(
    db_path: Path,
    conn: sqlite3.Connection,
    run_id: str,
    sqlite_json: dict[tuple[str, str, str], object],
) -> list[OutputHealthIssue]:
    issues: list[OutputHealthIssue] = []
    node_ids = {row[0] for row in conn.execute("SELECT id FROM risk_intel_nodes WHERE run_id = ?", (run_id,))}
    edge_ids = {row[0] for row in conn.execute("SELECT id FROM risk_intel_edges WHERE run_id = ?", (run_id,))}
    source_ids = {
        row[0] for row in conn.execute("SELECT id FROM risk_intel_source_records WHERE run_id = ?", (run_id,))
    }
    rule_ids = {row[0] for row in conn.execute("SELECT id FROM risk_intel_domain_rules WHERE run_id = ?", (run_id,))}

    for row in conn.execute(
        """
        SELECT id, source_id, target_id, evidence_refs_json, inference_refs_json, evidence_type
        FROM risk_intel_edges
        WHERE run_id = ?
        """,
        (run_id,),
    ):
        if row["source_id"] not in node_ids or row["target_id"] not in node_ids:
            issues.append(
                _issue(db_path, "risk_intel_sqlite_reference_mismatch", f"edge node reference missing: {row['id']}")
            )
        evidence_refs = _sqlite_json_list(sqlite_json, "risk_intel_edges", row["id"], "evidence_refs_json")
        if any(ref not in source_ids for ref in evidence_refs):
            issues.append(
                _issue(db_path, "risk_intel_sqlite_reference_mismatch", f"edge evidence reference missing: {row['id']}")
            )
        inference_refs = _sqlite_json_list(sqlite_json, "risk_intel_edges", row["id"], "inference_refs_json")
        if row["evidence_type"] == "inferred" and any(ref not in rule_ids for ref in inference_refs):
            issues.append(
                _issue(db_path, "risk_intel_sqlite_reference_mismatch", f"edge inference reference missing: {row['id']}")
            )

    for row in conn.execute(
        """
        SELECT id, path_node_ids_json, path_edge_ids_json
        FROM risk_intel_alert_paths
        WHERE run_id = ?
        """,
        (run_id,),
    ):
        path_node_ids = _sqlite_json_list(sqlite_json, "risk_intel_alert_paths", row["id"], "path_node_ids_json")
        path_edge_ids = _sqlite_json_list(sqlite_json, "risk_intel_alert_paths", row["id"], "path_edge_ids_json")
        if any(node_id not in node_ids for node_id in path_node_ids):
            issues.append(
                _issue(
                    db_path,
                    "risk_intel_sqlite_reference_mismatch",
                    f"alert path node reference missing: {row['id']}",
                )
            )
        if any(edge_id not in edge_ids for edge_id in path_edge_ids):
            issues.append(
                _issue(
                    db_path,
                    "risk_intel_sqlite_reference_mismatch",
                    f"alert path edge reference missing: {row['id']}",
                )
            )

    return issues


def _validate_manifest(db_path: Path, conn: sqlite3.Connection, run_id: str, root: Path) -> list[OutputHealthIssue]:
    issues: list[OutputHealthIssue] = []
    expected = {
        "risk_intel_graph": root / "risk_intel_graph.json",
        "risk_intel_summary": root / "risk_intel_summary.json",
        "risk_intel_refresh_log": root / "risk_intel_refresh_log.json",
    }
    rows = {
        row["artifact_name"]: row
        for row in conn.execute("SELECT * FROM risk_intel_export_manifest WHERE run_id = ?", (run_id,))
    }
    for artifact_name, path in expected.items():
        row = rows.get(artifact_name)
        if row is None:
            issues.append(_issue(db_path, "risk_intel_manifest_missing", f"missing manifest row: {artifact_name}"))
            continue
        manifest_path = str(row["path"])
        if not _manifest_path_matches_expected(manifest_path, path):
            issues.append(_issue(path, "risk_intel_manifest_mismatch", f"manifest path mismatch: {artifact_name}"))
        if not path.exists():
            issues.append(_issue(path, "risk_intel_manifest_mismatch", "manifested artifact is missing"))
            continue
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        try:
            byte_size = int(row["byte_size"])
        except (TypeError, ValueError):
            byte_size = -1
        if digest != row["sha256"] or len(content) != byte_size:
            issues.append(_issue(path, "risk_intel_manifest_mismatch", f"manifest mismatch: {artifact_name}"))
    return issues


def _manifest_path_matches_expected(manifest_path: str, expected_path: Path) -> bool:
    expected = expected_path.as_posix()
    if manifest_path == expected:
        return True
    return Path(manifest_path).as_posix() == expected
