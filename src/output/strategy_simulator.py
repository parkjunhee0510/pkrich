"""Write long-only strategy simulator output."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Any

from src.output.json_writer import write_json_file
from src.utils.signal_tracker import load_signal_rows
from src.utils.strategy_simulator import build_strategy_simulator


def write_strategy_simulator_output(*, output_root: Path | None = None) -> dict[str, Any]:
    root = output_root or Path("output")
    data_dir = root / "data"
    signal_rows = load_signal_rows(data_dir / "signal_tracker.csv")
    price_rows = _load_csv_rows(data_dir / "price_history.csv")
    payload = build_strategy_simulator(signal_rows, price_rows)
    path = data_dir / "strategy_simulator.json"
    write_json_file(path, payload)
    _sync_web_public(path, root.parent)
    return payload


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [
            {key.lstrip("\ufeff") if key else "": str(value) for key, value in row.items() if key}
            for row in csv.DictReader(handle)
        ]


def _sync_web_public(source_path: Path, project_root: Path) -> None:
    web_root = project_root / "web"
    if not web_root.exists() or not source_path.exists():
        return
    target_dir = web_root / "public" / "output" / "data"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_dir / source_path.name)
    except OSError:
        return
