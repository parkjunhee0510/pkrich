"""Serialize PolicyImpactReport to policy_impact.json (Task 7).

The report carries dataclasses; we walk them with `asdict` and emit a stable
dict structure that the dashboard / Web layer consumes. UTF-8, indent=2,
ensure_ascii=False so Korean rationale text stays human-readable.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict

from src.types import PolicyImpactReport


def write_policy_impact_json(report: PolicyImpactReport, path: str) -> None:
    """Write `report` to `path` as JSON. Creates parent directories as needed."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    payload = {
        "date": report.date,
        "events": [asdict(e) for e in report.events],
        "impacts_by_event": {
            k: [asdict(i) for i in v] for k, v in report.impacts_by_event.items()
        },
        "impacts_by_ticker": {
            k: [asdict(i) for i in v] for k, v in report.impacts_by_ticker.items()
        },
        "tailwind_scores": report.tailwind_scores,
        "metadata": report.metadata,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
