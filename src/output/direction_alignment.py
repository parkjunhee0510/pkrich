from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from src.output.schema import SCHEMA_VERSION
from src.utils.signal_tracker import load_signal_rows


def write_direction_alignment_output(*, output_root: Path | None = None, limit: int = 30) -> dict[str, Any]:
    root = output_root or Path("output")
    csv_path = root / "data" / "signal_tracker.csv"
    rows = load_signal_rows(csv_path)
    comparable = [
        row for row in rows
        if str(row.get("signal_direction", "")).strip() in {"bull", "bear", "neutral"}
        and str(row.get("llm_direction", "")).strip() in {"bull", "bear", "neutral"}
    ]
    agreement_count = sum(
        1 for row in comparable
        if str(row.get("signal_direction", "")).strip() == str(row.get("llm_direction", "")).strip()
    )
    conflict_rows = [
        {
            "signal_date": row.get("signal_date", ""),
            "ticker": row.get("ticker", ""),
            "signal_direction": row.get("signal_direction", ""),
            "llm_direction": row.get("llm_direction", ""),
            "catalyst_tag": row.get("catalyst_tag", ""),
            "conviction": row.get("conviction", ""),
            "action": row.get("action", ""),
            "regime": row.get("regime", ""),
        }
        for row in comparable
        if str(row.get("signal_direction", "")).strip() != str(row.get("llm_direction", "")).strip()
    ]
    pair_counts = Counter(
        (
            str(row.get("signal_direction", "")).strip(),
            str(row.get("llm_direction", "")).strip(),
        )
        for row in comparable
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "total_signals": len(rows),
            "comparable_signals": len(comparable),
            "agreement_count": agreement_count,
            "conflict_count": len(conflict_rows),
            "agreement_rate": round((agreement_count / len(comparable)) * 100, 1) if comparable else None,
            "latest_signal_date": max((str(row.get("signal_date", "")) for row in comparable), default=""),
        },
        "by_pair": [
            {
                "rule_direction": rule_direction,
                "llm_direction": llm_direction,
                "count": count,
            }
            for (rule_direction, llm_direction), count in sorted(
                pair_counts.items(),
                key=lambda item: (-item[1], item[0][0], item[0][1]),
            )
        ],
        "recent_conflicts": sorted(
            conflict_rows,
            key=lambda row: (str(row.get("signal_date", "")), str(row.get("ticker", ""))),
            reverse=True,
        )[:limit],
    }

    path = root / "data" / "direction_alignment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _sync_web_public(path, root.parent)
    return payload


def _sync_web_public(source_path: Path, project_root: Path) -> None:
    web_root = project_root / "web"
    if not web_root.exists() or not source_path.exists():
        return
    target_dir = web_root / "public" / "output" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_dir / source_path.name)
