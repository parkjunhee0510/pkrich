"""Deterministic JSON writer for generated output artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonWriteError(RuntimeError):
    """Raised when an output JSON payload cannot be safely written."""


def write_json_file(path: Path, payload: Any, *, indent: int = 2) -> None:
    """Write JSON and immediately parse it back."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = json.dumps(payload, ensure_ascii=False, indent=indent)
    except (TypeError, ValueError) as exc:
        raise JsonWriteError(f"payload for {path} is not JSON serializable: {exc}") from exc

    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        raise JsonWriteError(f"serialized payload for {path} is invalid JSON: {exc}") from exc

    path.write_text(text, encoding="utf-8")

    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise JsonWriteError(f"written payload for {path} failed parse-back: {exc}") from exc
