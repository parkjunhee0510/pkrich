from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Iterable

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.data_sources import AuditDataset


_STRICT_TICKER_HASH_FIELDS = ("raw_payload_hash", "macro_context_hash", "market_regime_hash")


class R3EvidenceConsistency(BaseCheck):
    check_id = "R3"
    dimension = "evidence_consistency"

    def run(self, dataset: AuditDataset) -> CheckResult:
        records = _all_records(dataset)
        if not records:
            return CheckResult(
                check_id=self.check_id,
                severity="info",
                pass_rate=0.0,
                findings=(),
                metrics={
                    "total_records": 0.0,
                    "evaluated_groups": 0.0,
                    "mismatch_count": 0.0,
                    "warning_count": 0.0,
                },
                recommendation="No LLM evidence manifest records were found for this audit window.",
            )

        findings: list[Finding] = []
        warnings: list[Finding] = []
        evaluated_groups = 0

        ticker_groups = _group_records(
            [row for _d, row in records if row.get("scope") == "ticker"],
            key_fields=("run_date", "ticker"),
        )
        for (run_date_text, ticker), group in ticker_groups.items():
            evaluated_groups += 1
            for field in _STRICT_TICKER_HASH_FIELDS:
                values = {str(row.get(field, "")) for row in group if row.get(field)}
                if len(values) > 1:
                    findings.append(
                        Finding(
                            ticker=str(ticker),
                            date=_parse_date(run_date_text),
                            module="llm_evidence",
                            jsonpath=f"$.{field}",
                            detail={"field": field, "values": sorted(values)},
                        )
                    )

        committee_groups = _group_records(
            [row for _d, row in records if row.get("scope") == "committee_role"],
            key_fields=("run_date", "ticker", "round"),
        )
        for (run_date_text, ticker, round_name), group in committee_groups.items():
            evaluated_groups += 1
            analysis_hashes = {
                str(row.get("analysis_payload_hash", ""))
                for row in group
                if row.get("analysis_payload_hash")
            }
            if len(analysis_hashes) > 1:
                findings.append(
                    Finding(
                        ticker=str(ticker),
                        date=_parse_date(run_date_text),
                        module="committee",
                        jsonpath="$.analysis_payload_hash",
                        detail={"round": round_name, "values": sorted(analysis_hashes)},
                    )
                )
            for row in group:
                if row.get("macro_context_present") is False or row.get("market_regime_present") is False:
                    warnings.append(
                        Finding(
                            ticker=str(ticker),
                            date=_parse_date(run_date_text),
                            module=str(row.get("module", "committee")),
                            jsonpath="$.macro_context_present",
                            detail={
                                "reason": "committee_macro_or_regime_linkage_missing",
                                "role": row.get("role"),
                                "round": round_name,
                            },
                        )
                    )

        mismatch_count = len(findings)
        warning_count = len(warnings)
        if mismatch_count:
            severity = "fail"
        elif warning_count:
            severity = "warn"
        else:
            severity = "pass"
        pass_rate = 1.0 if evaluated_groups == 0 else max(
            0.0,
            (evaluated_groups - mismatch_count) / evaluated_groups,
        )
        return CheckResult(
            check_id=self.check_id,
            severity=severity,
            pass_rate=pass_rate,
            findings=tuple([*findings, *warnings]),
            metrics={
                "total_records": float(len(records)),
                "evaluated_groups": float(evaluated_groups),
                "mismatch_count": float(mismatch_count),
                "warning_count": float(warning_count),
            },
            recommendation=(
                "Compare evidence manifest hashes for the affected ticker and rerun the pipeline from collection "
                "if economy, deep, or committee records used different source evidence."
            ),
        )


def _all_records(dataset: AuditDataset) -> list[tuple[date, dict[str, Any]]]:
    out: list[tuple[date, dict[str, Any]]] = []
    for d, rows in dataset.llm_evidence.items():
        for row in rows:
            out.append((d, dict(row)))
    return out


def _group_records(
    records: Iterable[dict[str, Any]],
    *,
    key_fields: tuple[str, ...],
) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        key = tuple(row.get(field) for field in key_fields)
        grouped[key].append(row)
    return grouped


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
