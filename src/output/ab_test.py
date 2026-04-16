from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def write_ab_test_results(
    payload: dict[str, Any],
    *,
    output_root: Path | None = None,
) -> Path:
    root = output_root or Path("output")
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "ab_test_results.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _sync_web_public_data(data_dir, root.parent)
    return path


def _sync_web_public_data(data_dir: Path, project_root: Path) -> None:
    web_root = project_root / "web"
    if not web_root.exists():
        return
    target_dir = web_root / "public" / "output" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)
    source_path = data_dir / "ab_test_results.json"
    if source_path.exists():
        shutil.copy2(source_path, target_dir / "ab_test_results.json")
