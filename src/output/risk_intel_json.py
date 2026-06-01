"""Write risk intelligence graph artifacts."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from src.output.json_export import _sync_web_public_data
from src.output.json_writer import write_json_file
from src.output.risk_intel_builder import build_risk_intel_artifacts
from src.output.risk_intel_exporter import export_risk_intel_artifacts
from src.output.risk_intel_store import (
    RISK_INTEL_DB_FILENAME,
    checkpoint_store,
    record_export_manifest,
    replace_graph_run,
)
from src.types import PortfolioSummary, WatchlistItem


_ARTIFACT_FILES = {
    "risk_intel_graph": "risk_intel_graph.json",
    "risk_intel_summary": "risk_intel_summary.json",
    "risk_intel_refresh_log": "risk_intel_refresh_log.json",
}
_ARTIFACT_PAYLOAD_KEYS = {
    "risk_intel_graph": "graph",
    "risk_intel_summary": "summary",
    "risk_intel_refresh_log": "refresh_log",
}


def write_risk_intel_outputs(
    *,
    output_root: Path = Path("output"),
    project_root: Path | None = None,
    run_date: date,
    policy_payload: dict[str, Any] | None,
    search_evidence_payload: dict[str, Any] | None,
    watchlist: list[WatchlistItem],
    portfolio_summary: PortfolioSummary | None,
    sector_payload: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    data_dir = output_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / RISK_INTEL_DB_FILENAME

    built = build_risk_intel_artifacts(
        run_date=run_date,
        policy_payload=policy_payload,
        search_evidence_payload=search_evidence_payload,
        watchlist=watchlist,
        portfolio_summary=portfolio_summary,
        sector_payload=sector_payload,
    )
    with tempfile.TemporaryDirectory(dir=data_dir, prefix=".risk_intel_txn_") as rollback_root:
        rollback_dir = Path(rollback_root)
        db_backup = _capture_sqlite_backup(db_path, rollback_dir)
        json_backups = _capture_json_backups(data_dir, rollback_dir)
        try:
            replace_graph_run(db_path, built)
            artifacts = export_risk_intel_artifacts(db_path, run_id=str(built["graph"]["generation"]["run_id"]))

            _write_risk_intel_json_files(data_dir, artifacts)
            record_export_manifest(
                db_path,
                str(artifacts["graph"]["generation"]["run_id"]),
                _build_manifest(data_dir),
                exported_at=str(artifacts["graph"]["generation"]["generated_at"]),
            )
            checkpoint_store(db_path)
            _sync_web_public_data(data_dir, project_root or output_root.parent)
        except Exception as exc:
            try:
                _restore_json_backups(json_backups)
                _restore_sqlite_backup(db_path, db_backup)
            except Exception as rollback_exc:
                if hasattr(exc, "add_note"):
                    exc.add_note(f"risk intel output rollback failed: {rollback_exc}")
            raise
    return artifacts


def _capture_sqlite_backup(db_path: Path, backup_dir: Path) -> tuple[bool, Path]:
    backup_path = backup_dir / f".backup_{db_path.name}"
    if db_path.exists():
        checkpoint_store(db_path)
        shutil.copy2(db_path, backup_path)
        return True, backup_path
    return False, backup_path


def _restore_sqlite_backup(db_path: Path, backup: tuple[bool, Path]) -> None:
    existed, backup_path = backup
    _remove_sqlite_sidecars(db_path)
    if existed:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, db_path)
    else:
        db_path.unlink(missing_ok=True)
    _remove_sqlite_sidecars(db_path)


def _remove_sqlite_sidecars(db_path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)


def _capture_json_backups(data_dir: Path, backup_dir: Path) -> dict[str, tuple[bool, Path]]:
    backups: dict[str, tuple[bool, Path]] = {}
    for filename in _ARTIFACT_FILES.values():
        final_path = data_dir / filename
        backup_path = backup_dir / f".backup_{filename}"
        if final_path.exists():
            shutil.copy2(final_path, backup_path)
            backups[filename] = (True, backup_path)
        else:
            backups[filename] = (False, backup_path)
    return backups


def _restore_json_backups(backups: dict[str, tuple[bool, Path]]) -> None:
    for filename, (existed, backup_path) in backups.items():
        final_path = backup_path.parent.parent / filename
        if existed:
            shutil.copy2(backup_path, final_path)
        else:
            final_path.unlink(missing_ok=True)


def _write_risk_intel_json_files(data_dir: Path, artifacts: dict[str, dict[str, Any]]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=data_dir, prefix=".risk_intel_staging_") as staging_root:
        staging_dir = Path(staging_root)
        staged_paths: dict[str, Path] = {}
        for artifact_name, filename in _ARTIFACT_FILES.items():
            staged_path = staging_dir / filename
            write_json_file(staged_path, artifacts[_ARTIFACT_PAYLOAD_KEYS[artifact_name]])
            staged_paths[filename] = staged_path

        _promote_staged_json_files(data_dir, staged_paths)


def _promote_staged_json_files(data_dir: Path, staged_paths: dict[str, Path]) -> None:
    if not staged_paths:
        return

    staging_dir = next(iter(staged_paths.values())).parent
    backups: dict[str, tuple[bool, Path]] = {}
    for filename in staged_paths:
        final_path = data_dir / filename
        backup_path = staging_dir / f".backup_{filename}"
        if final_path.exists():
            shutil.copy2(final_path, backup_path)
            backups[filename] = (True, backup_path)
        else:
            backups[filename] = (False, backup_path)

    try:
        for filename, staged_path in staged_paths.items():
            _replace_file(staged_path, data_dir / filename)
    except Exception as exc:
        # SQLite is already canonical for the attempted run; this restores only public JSON files.
        try:
            _restore_json_file_backups(data_dir, backups)
        except Exception as rollback_exc:
            if hasattr(exc, "add_note"):
                exc.add_note(f"risk intel JSON rollback failed: {rollback_exc}")
        raise


def _restore_json_file_backups(data_dir: Path, backups: dict[str, tuple[bool, Path]]) -> None:
    for filename, (existed, backup_path) in backups.items():
        final_path = data_dir / filename
        if existed:
            _replace_file(backup_path, final_path)
        else:
            final_path.unlink(missing_ok=True)


def _replace_file(source: Path, target: Path) -> None:
    source.replace(target)


def _build_manifest(data_dir: Path) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for artifact_name, filename in _ARTIFACT_FILES.items():
        path = data_dir / filename
        content = path.read_bytes()
        manifest[artifact_name] = {
            "path": path.as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(),
            "byte_size": len(content),
        }
    return manifest
