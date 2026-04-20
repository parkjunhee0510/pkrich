from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def normalize_json_shape(value: Any) -> Any:
    if value is None:
        return {"__type__": "null"}
    if isinstance(value, bool):
        return {"__type__": "bool"}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"__type__": "int"}
    if isinstance(value, float):
        return {"__type__": "float"}
    if isinstance(value, str):
        return {"__type__": "str"}
    if isinstance(value, list):
        return {
            "__type__": "array",
            "item": normalize_json_shape(value[0]) if value else {"__type__": "empty"},
        }
    if isinstance(value, dict):
        return {
            "__type__": "object",
            "keys": {
                str(key): normalize_json_shape(item)
                for key, item in sorted(value.items(), key=lambda kv: str(kv[0]))
            },
        }
    return {"__type__": type(value).__name__}


def load_snapshot_fixture(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
