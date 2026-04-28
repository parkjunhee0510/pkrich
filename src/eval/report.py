from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.eval.checks.base import CheckResult


SEVERITY_ICON = {"pass": "OK", "warn": "WARN", "fail": "FAIL", "info": "i"}


def _summary_counts(results: Sequence[CheckResult]) -> dict[str, Any]:
    counts: dict[str, Any] = {"pass": 0, "warn": 0, "fail": 0, "info": 0}
    for r in results:
        counts[r.severity] += 1
    counts["total_checks"] = len(results)
    counts["overall_severity"] = (
        "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    )
    return counts


def render_json(
    *,
    audit_date: date,
    window_start: date,
    window_end: date,
    tickers: Sequence[str],
    model_profile: str,
    git_sha: str,
    replay_meta: Mapping[str, Any],
    results: Sequence[CheckResult],
) -> dict[str, Any]:
    counts = _summary_counts(results)
    return {
        "schema_version": 1,
        "audit_date": audit_date.isoformat(),
        "window": {
            "start": window_start.isoformat(),
            "end": window_end.isoformat(),
            "days": (window_end - window_start).days + 1,
        },
        "tickers_audited": list(tickers),
        "model_profile": model_profile,
        "git_sha": git_sha,
        "replay": dict(replay_meta),
        "summary": {
            "total_checks": counts["total_checks"],
            "pass": counts["pass"],
            "warn": counts["warn"],
            "fail": counts["fail"],
            "overall_severity": counts["overall_severity"],
        },
        "checks": [
            {
                "check_id": r.check_id,
                "severity": r.severity,
                "pass_rate": r.pass_rate,
                "metrics": dict(r.metrics),
                "findings": [
                    {
                        "ticker": f.ticker,
                        "date": f.date.isoformat() if f.date else None,
                        "module": f.module,
                        "jsonpath": f.jsonpath,
                        "detail": dict(f.detail),
                    }
                    for f in r.findings
                ],
                "recommendation": r.recommendation,
            }
            for r in results
        ],
    }


def render_markdown(
    *,
    audit_date: date,
    window_start: date,
    window_end: date,
    tickers: Sequence[str],
    replay_meta: Mapping[str, Any],
    results: Sequence[CheckResult],
) -> str:
    counts = _summary_counts(results)
    days = (window_end - window_start).days + 1
    cost = float(replay_meta.get("cost_usd", 0.0))
    lines: list[str] = []
    lines.append(f"# LLM Audit Report — {audit_date.isoformat()}")
    lines.append("")
    lines.append(
        f"**Window:** {window_start.isoformat()} ~ {window_end.isoformat()} ({days}d) | "
        f"**Tickers:** {len(tickers)} | **Replay cost:** ${cost:.2f}"
    )
    lines.append(
        f"**Overall verdict:** {counts['fail']} fail / {counts['warn']} warn / "
        f"{counts['pass']} pass (out of {counts['total_checks']})"
    )
    lines.append("")
    lines.append("## Verdict Matrix")
    lines.append("")
    lines.append("| ID | Severity | Pass rate | Top metric |")
    lines.append("|----|----------|-----------|------------|")
    for r in results:
        metric_kv = next(iter(r.metrics.items()), ("-", 0.0))
        lines.append(
            f"| {r.check_id} | {SEVERITY_ICON[r.severity]} {r.severity} | "
            f"{r.pass_rate * 100:.1f}% | {metric_kv[0]}={metric_kv[1]:.3f} |"
        )
    lines.append("")
    lines.append("## 차원별 상세")
    for r in results:
        lines.append("")
        lines.append(f"### {r.check_id} — severity: {r.severity}")
        for k, v in r.metrics.items():
            lines.append(f"- {k}: {v:.4f}")
        if r.findings:
            lines.append("")
            lines.append("Top findings:")
            for f in r.findings[:10]:
                lines.append(
                    f"- ticker={f.ticker} date={f.date} jsonpath={f.jsonpath} detail={dict(f.detail)}"
                )
        if r.recommendation:
            lines.append("")
            lines.append(f"**Recommendation:** {r.recommendation}")
    return "\n".join(lines) + "\n"


def write_artifacts(
    *,
    root: Path,
    audit_date: date,
    window_start: date,
    window_end: date,
    tickers: Sequence[str],
    model_profile: str,
    git_sha: str,
    replay_meta: Mapping[str, Any],
    results: Sequence[CheckResult],
    suffix: str | None = None,
) -> tuple[Path, Path]:
    suf = f"-{suffix}" if suffix else ""
    md_path = root / "docs" / "reports" / f"llm-audit-{audit_date.isoformat()}{suf}.md"
    json_path = root / "output" / "data" / "llm_audit" / f"{audit_date.isoformat()}{suf}.json"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    md_path.write_text(render_markdown(
        audit_date=audit_date, window_start=window_start, window_end=window_end,
        tickers=tickers, replay_meta=replay_meta, results=results,
    ), encoding="utf-8")
    json_path.write_text(json.dumps(render_json(
        audit_date=audit_date, window_start=window_start, window_end=window_end,
        tickers=tickers, model_profile=model_profile, git_sha=git_sha,
        replay_meta=replay_meta, results=results,
    ), ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path
