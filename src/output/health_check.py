"""Health checks for generated output artifacts and web mirrors."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.output.web_sync_contract import iter_web_sync_relative_paths


_CONFLICT_MARKERS = ("<<<<<<< ", "=======", ">>>>>>> ")
_CONFLICT_MARKER_SUFFIXES = {".json", ".csv", ".md"}


@dataclass(frozen=True)
class OutputHealthIssue:
    code: str
    path: str
    detail: str


@dataclass(frozen=True)
class OutputHealthResult:
    issues: tuple[OutputHealthIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def format_summary(self, *, max_issues: int = 50) -> str:
        if self.ok:
            return "output health check passed"
        lines = [f"output health check failed: {len(self.issues)} issue(s)"]
        for issue in self.issues[:max_issues]:
            lines.append(f"- {issue.code}: {issue.path} ({issue.detail})")
        remaining = len(self.issues) - max_issues
        if remaining > 0:
            lines.append(f"- ... {remaining} more issue(s)")
        return "\n".join(lines)


def check_output_health(
    project_root: str | Path = ".",
    *,
    source_data_dir: str | Path | None = None,
    web_data_dir: str | Path | None = None,
) -> OutputHealthResult:
    """Validate generated JSON and default web-public mirror consistency."""
    root = Path(project_root)
    source_root = Path(source_data_dir) if source_data_dir is not None else root / "output" / "data"
    mirror_root = Path(web_data_dir) if web_data_dir is not None else root / "web" / "public" / "output" / "data"

    issues: list[OutputHealthIssue] = []
    issues.extend(_validate_json_tree(source_root, label="output_data"))
    issues.extend(_validate_json_tree(mirror_root, label="web_public_output_data"))
    issues.extend(_detect_conflict_markers(source_root))
    issues.extend(_detect_conflict_markers(mirror_root))
    issues.extend(_compare_web_mirror(source_root, mirror_root))
    return OutputHealthResult(tuple(issues))


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
