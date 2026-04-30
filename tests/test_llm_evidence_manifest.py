from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.analyzer.evidence_manifest import (
    canonical_json,
    evidence_hash,
    prompt_template_hash,
    write_evidence_record,
)
from src.analyzer.prompts.base import PromptTemplate


def test_evidence_hash_is_stable_for_key_order_and_dates() -> None:
    left = {"b": 2, "a": date(2026, 4, 30)}
    right = {"a": date(2026, 4, 30), "b": 2}

    left_hash, left_present = evidence_hash(left)
    right_hash, right_present = evidence_hash(right)

    assert left_present is True
    assert right_present is True
    assert left_hash == right_hash
    assert left_hash.startswith("sha256:")


def test_evidence_hash_distinguishes_missing_from_empty_object() -> None:
    missing_hash, missing_present = evidence_hash(None)
    empty_hash, empty_present = evidence_hash({})

    assert missing_present is False
    assert empty_present is True
    assert missing_hash != empty_hash


def test_prompt_template_hash_uses_template_identity() -> None:
    template = PromptTemplate(
        name="signal_takeaway_module",
        version="research_v1",
        system_template="system",
        user_template="{batch_payload_json}",
        output_schema={"type": "object"},
    )

    digest = prompt_template_hash(template)

    assert digest.startswith("sha256:")


def test_prompt_template_hash_changes_when_identity_fields_change() -> None:
    base = PromptTemplate(
        name="signal_takeaway_module",
        version="research_v1",
        system_template="system",
        user_template="{batch_payload_json}",
        output_schema={"type": "object"},
    )
    changed_version = PromptTemplate(
        name="signal_takeaway_module",
        version="research_v2",
        system_template="system",
        user_template="{batch_payload_json}",
        output_schema={"type": "object"},
    )
    changed_schema = PromptTemplate(
        name="signal_takeaway_module",
        version="research_v1",
        system_template="system",
        user_template="{batch_payload_json}",
        output_schema={"type": "object", "required": ["ticker"]},
    )

    digest = prompt_template_hash(base)

    assert prompt_template_hash(changed_version) != digest
    assert prompt_template_hash(changed_schema) != digest


def test_canonical_json_sorts_sets_deterministically() -> None:
    assert canonical_json({"values": {"beta", "alpha", "gamma"}}) == (
        '{"values":["alpha","beta","gamma"]}'
    )


def test_canonical_json_preserves_naive_datetime_without_timezone_conversion() -> None:
    naive = datetime(2026, 4, 30, 9, 15, 30)

    left_hash, left_present = evidence_hash({"at": naive})
    right_hash, right_present = evidence_hash({"at": datetime(2026, 4, 30, 9, 15, 30)})

    assert canonical_json({"at": naive}) == '{"at":"2026-04-30T09:15:30"}'
    assert left_present is True
    assert right_present is True
    assert left_hash == right_hash


def test_write_evidence_record_writes_jsonl_and_sanitizes_raw_text(tmp_path: Path) -> None:
    write_evidence_record(
        {
            "run_date": "2026-04-30",
            "stage": "analyzer",
            "scope": "ticker",
            "module": "signal_takeaway_module",
            "ticker": "AAPL",
            "raw_prompt": "do not persist",
            "model_response": "do not persist",
            "created_at": datetime(2026, 4, 30, tzinfo=timezone.utc).isoformat(),
        },
        run_date="2026-04-30",
        output_root=tmp_path / "output",
    )

    path = tmp_path / "output" / "data" / "llm_evidence" / "2026-04-30.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert len(rows) == 1
    assert rows[0]["schema_version"] == 1
    assert rows[0]["module"] == "signal_takeaway_module"
    assert "raw_prompt" not in rows[0]
    assert "model_response" not in rows[0]


def test_write_evidence_record_recursively_sanitizes_sensitive_keys(tmp_path: Path) -> None:
    write_evidence_record(
        {
            "run_date": "2026-04-30",
            "module": "signal_takeaway_module",
            "request": {
                "raw_prompt": "secret prompt",
                "messages": [{"role": "user", "content": "secret content"}],
                "headers": {"Api_Key": "secret key"},
            },
            "response": {
                "Raw_Response": "secret raw",
                "response_body": "secret body",
                "safe_count": 2,
            },
        },
        run_date="2026-04-30",
        output_root=tmp_path / "output",
    )

    path = tmp_path / "output" / "data" / "llm_evidence" / "2026-04-30.jsonl"
    persisted = path.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in persisted.splitlines()]

    assert len(rows) == 1
    assert "secret" not in persisted
    assert rows[0]["request"]["messages"] == [{"role": "user"}]
    assert rows[0]["response"] == {"safe_count": 2}


def test_write_evidence_record_failure_is_best_effort(tmp_path: Path) -> None:
    with (
        patch("pathlib.Path.mkdir", side_effect=OSError("blocked")),
        patch("src.analyzer.evidence_manifest.record_pipeline_event") as record_event,
    ):
        ok = write_evidence_record(
            {"run_date": "2026-04-30", "module": "x"},
            run_date="2026-04-30",
            output_root=tmp_path / "output",
        )

    assert ok is False
    record_event.assert_called_once()
    assert record_event.call_args.args[:3] == ("analyzer", "warning", "llm_evidence_write_failed")


def test_write_evidence_record_still_returns_false_when_failure_logging_fails(tmp_path: Path) -> None:
    with (
        patch("pathlib.Path.mkdir", side_effect=OSError("blocked")),
        patch("src.analyzer.evidence_manifest.record_pipeline_event", side_effect=RuntimeError("log failed")),
    ):
        ok = write_evidence_record(
            {"run_date": "2026-04-30", "module": "x"},
            run_date="2026-04-30",
            output_root=tmp_path / "output",
        )

    assert ok is False


def test_write_evidence_record_rejects_run_date_path_separators(tmp_path: Path) -> None:
    with patch("src.analyzer.evidence_manifest.record_pipeline_event") as record_event:
        ok = write_evidence_record(
            {"run_date": "../2026-04-30", "module": "x"},
            run_date="../2026-04-30",
            output_root=tmp_path / "output",
        )

    assert ok is False
    assert not (tmp_path / "output" / "data" / "2026-04-30.jsonl").exists()
    record_event.assert_called_once()
