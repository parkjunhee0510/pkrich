from __future__ import annotations

import hashlib
import json
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.analyzer.prompts.base import PromptTemplate
from src.utils.pipeline_logging import record_pipeline_event


SCHEMA_VERSION = 1
_WRITE_LOCK = threading.Lock()
_BLOCKED_KEYS = {
    "raw_prompt",
    "system_prompt",
    "user_prompt",
    "model_response",
    "response_text",
    "api_key",
}


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple | set):
        return list(value)
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def evidence_hash(value: Any) -> tuple[str, bool]:
    present = value is not None
    normalized = {"__missing__": True} if value is None else value
    digest = hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()
    return f"sha256:{digest}", present


def prompt_template_hash(template: PromptTemplate) -> str:
    digest, _present = evidence_hash(
        {
            "name": template.name,
            "version": template.version,
            "system_template": template.system_template,
            "user_template": template.user_template,
            "output_schema": template.output_schema,
        }
    )
    return digest


def generic_hash(value: Any) -> str:
    digest, _present = evidence_hash(value)
    return digest


def _sanitize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in record.items():
        if key.lower() in _BLOCKED_KEYS:
            continue
        sanitized[key] = value
    if "schema_version" not in sanitized:
        sanitized["schema_version"] = SCHEMA_VERSION
    if "created_at" not in sanitized:
        sanitized["created_at"] = datetime.now(timezone.utc).isoformat()
    return sanitized


def write_evidence_record(
    record: Mapping[str, Any],
    *,
    run_date: str | date,
    output_root: Path = Path("output"),
) -> bool:
    date_text = run_date.isoformat() if isinstance(run_date, date) else str(run_date)
    path = output_root / "data" / "llm_evidence" / f"{date_text}.jsonl"
    try:
        payload = _sanitize_record(record)
        line = canonical_json(payload)
        with _WRITE_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return True
    except Exception as exc:
        record_pipeline_event(
            "analyzer",
            "warning",
            "llm_evidence_write_failed",
            error_type=type(exc).__name__,
            error_message=str(exc)[:200],
            module=str(record.get("module", "")),
            ticker=str(record.get("ticker", "")),
        )
        return False
