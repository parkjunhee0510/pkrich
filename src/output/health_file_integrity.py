"""Health checks for output file integrity and web mirrors."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from src.output.health_common import OutputHealthIssue
from src.output.web_sync_contract import iter_web_sync_relative_paths


_CONFLICT_MARKERS = ("<<<<<<< ", "=======", ">>>>>>> ")
_CONFLICT_MARKER_SUFFIXES = {".json", ".csv", ".md"}


def _validate_json_tree(root: Path, *, label: str) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return (OutputHealthIssue("missing_dir", str(root), f"{label} directory is missing"),)

    issues: list[OutputHealthIssue] = []
    for path in sorted(root.rglob("*.json")):
        try:
            with path.open(encoding="utf-8") as handle:
                json.load(handle)
        except Exception as exc:
            issues.append(OutputHealthIssue("invalid_json", str(path), str(exc)))
    return tuple(issues)


def _detect_conflict_markers(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    issues: list[OutputHealthIssue] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _CONFLICT_MARKER_SUFFIXES:
            continue
        try:
            with path.open(encoding="utf-8") as handle:
                for line_no, line in enumerate(handle, start=1):
                    if any(line.startswith(marker) for marker in _CONFLICT_MARKERS):
                        issues.append(
                            OutputHealthIssue(
                                "merge_conflict_marker",
                                str(path),
                                f"marker at line {line_no}",
                            )
                        )
                        break
        except UnicodeDecodeError:
            continue
    return tuple(issues)


def _compare_web_mirror(source_root: Path, mirror_root: Path) -> Iterable[OutputHealthIssue]:
    if not source_root.exists():
        return ()
    if not mirror_root.exists():
        return (OutputHealthIssue("missing_dir", str(mirror_root), "web public mirror directory is missing"),)

    issues: list[OutputHealthIssue] = []
    expected = set(iter_web_sync_relative_paths(source_root))
    for rel_path in sorted(expected):
        source_path = source_root / rel_path
        mirror_path = mirror_root / rel_path
        if not mirror_path.exists():
            issues.append(OutputHealthIssue("mirror_missing", str(mirror_path), f"missing mirror for {rel_path.as_posix()}"))
            continue
        if _sha256(source_path) != _sha256(mirror_path):
            issues.append(OutputHealthIssue("mirror_mismatch", str(mirror_path), f"differs from {source_path}"))

    mirror_tickers = mirror_root / "tickers"
    if mirror_tickers.is_dir():
        for path in sorted(mirror_tickers.rglob("*")):
            if not path.is_file():
                continue
            rel_path = path.relative_to(mirror_root)
            if rel_path not in expected:
                issues.append(OutputHealthIssue("mirror_extra", str(path), "extra ticker mirror file"))

    return tuple(issues)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
