"""Write search audit JSON artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.output.json_export import _sync_web_public_data


def write_search_audit_output(payload: dict[str, Any], *, output_root: Path = Path("output")) -> Path:
    data_dir = output_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "search_audit.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _sync_web_public_data(data_dir, data_dir.parent.parent)
    return path
