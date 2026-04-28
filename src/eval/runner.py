from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import (
    ALL_CHECK_IDS,
    DEFAULT_MAX_REPLAY_COST_USD,
    DEFAULT_REPLAY_TICKERS,
    DEFAULT_RUNS_PER_TICKER,
    DEFAULT_WINDOW_DAYS,
)
from src.eval.data_sources import load_window
from src.eval.report import write_artifacts


logger = logging.getLogger(__name__)


@dataclass
class RunnerConfig:
    root: Path
    audit_date: date
    window_days: int
    tickers: list[str]
    checks: Sequence[str]
    skip_replay: bool
    model_profile: str
    git_sha: str
    suffix: str | None = None
    max_replay_cost_usd: float = DEFAULT_MAX_REPLAY_COST_USD
    replay_tickers: tuple[str, ...] = DEFAULT_REPLAY_TICKERS
    runs_per_ticker: int = DEFAULT_RUNS_PER_TICKER
    dry_run: bool = False
    check_links: bool = False
    check_overrides: Mapping[str, BaseCheck] = field(default_factory=dict)


def _build_check(check_id: str, cfg: "RunnerConfig") -> BaseCheck:
    if check_id in cfg.check_overrides:
        return cfg.check_overrides[check_id]
    if check_id == "I1":
        from src.eval.checks.i1_schema_stability import I1SchemaStability
        return I1SchemaStability()
    if check_id == "I2":
        from src.eval.checks.i2_missingness import I2Missingness
        return I2Missingness()
    if check_id == "I3":
        from src.eval.checks.i3_format_consistency import I3FormatConsistency
        return I3FormatConsistency()
    if check_id == "I4":
        from src.eval.checks.i4_input_size_drift import I4InputSizeDrift
        return I4InputSizeDrift()
    if check_id == "O1":
        from src.eval.checks.o1_schema_compliance import O1SchemaCompliance
        return O1SchemaCompliance()
    if check_id == "O2":
        from src.eval.checks.o2_numeric_grounding import O2NumericGrounding
        return O2NumericGrounding()
    if check_id == "O3":
        from src.eval.checks.o3_citation_integrity import O3CitationIntegrity
        return O3CitationIntegrity(check_links=cfg.check_links)
    if check_id == "O4":
        from src.eval.checks.o4_language_consistency import O4LanguageConsistency
        return O4LanguageConsistency()
    if check_id == "O5":
        from src.eval.checks.o5_contradiction import O5Contradiction
        return O5Contradiction()
    if check_id == "D2":
        from src.eval.checks.d2_committee_agreement import D2CommitteeAgreement
        return D2CommitteeAgreement()
    if check_id == "D3":
        from src.eval.checks.d3_signal_volatility import D3SignalVolatility
        return D3SignalVolatility()
    if check_id == "R1":
        from src.eval.checks.r1_pipeline_summary import R1PipelineSummary
        return R1PipelineSummary()
    if check_id == "R2":
        from src.eval.checks.r2_retry_distribution import R2RetryDistribution
        return R2RetryDistribution()
    if check_id == "D1":
        if cfg.skip_replay:
            class _Skipped(BaseCheck):
                check_id = "D1"
                dimension = "semantic_drift"

                def run(self, ds: Any) -> CheckResult:
                    return CheckResult(
                        check_id="D1", severity="info", pass_rate=0.0,
                        findings=(), metrics={"skipped": 1.0},
                        recommendation="Run without --skip-replay to enable drift check.",
                    )
            return _Skipped()
        from src.eval.checks.d1_semantic_drift import D1SemanticDrift
        from src.eval.replay import OpenAIReplayClient
        return D1SemanticDrift(
            client=OpenAIReplayClient(model_profile=cfg.model_profile),
            replay_tickers=cfg.replay_tickers,
            runs_per_ticker=cfg.runs_per_ticker,
            max_cost_usd=cfg.max_replay_cost_usd,
            dry_run=cfg.dry_run,
        )
    raise KeyError(f"Unknown check_id: {check_id}")


def _error_result(check_id: str, exc: BaseException) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        severity="fail",
        pass_rate=0.0,
        findings=(Finding(detail={"error": str(exc), "trace": traceback.format_exc()}),),
        metrics={},
        recommendation="Check raised an exception; see findings[0].detail.trace",
    )


def _exit_code_from_results(results: Sequence[CheckResult]) -> int:
    if any(r.severity == "fail" for r in results):
        return 2
    if any(r.severity == "warn" for r in results):
        return 1
    return 0


def run_audit(cfg: RunnerConfig) -> tuple[int, list[CheckResult]]:
    if cfg.window_days < 1:
        raise ValueError(f"window_days must be >= 1, got {cfg.window_days}")

    dataset = load_window(
        root=cfg.root, end=cfg.audit_date, window_days=cfg.window_days,
        tickers=cfg.tickers, model_profile=cfg.model_profile,
    )

    results: list[CheckResult] = []
    for check_id in cfg.checks:
        try:
            check = _build_check(check_id, cfg)
            print(f"[{check_id}] running...", flush=True)
            results.append(check.run(dataset))
        except BaseException as exc:
            logger.exception("Check %s raised", check_id)
            results.append(_error_result(check_id, exc))

    write_artifacts(
        root=cfg.root, audit_date=cfg.audit_date,
        window_start=dataset.window_start, window_end=dataset.window_end,
        tickers=dataset.tickers, model_profile=cfg.model_profile,
        git_sha=cfg.git_sha,
        replay_meta={
            "enabled": not cfg.skip_replay,
            "tickers": list(cfg.replay_tickers),
            "runs_per_ticker": cfg.runs_per_ticker,
            "cost_usd": 0.0,
            "cost_cap_usd": cfg.max_replay_cost_usd,
        },
        results=results,
        suffix=cfg.suffix,
    )
    return _exit_code_from_results(results), results


def _git_sha(root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=root, stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="src.eval.runner",
                                description="LLM quality audit (one-shot).")
    p.add_argument("--window", type=int, default=DEFAULT_WINDOW_DAYS)
    p.add_argument("--checks", type=str, default=",".join(ALL_CHECK_IDS))
    p.add_argument("--skip-replay", action="store_true")
    p.add_argument("--replay-tickers", type=str, default=",".join(DEFAULT_REPLAY_TICKERS))
    p.add_argument("--max-replay-cost-usd", type=float,
                   default=DEFAULT_MAX_REPLAY_COST_USD)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--suffix", type=str, default=None)
    p.add_argument("--check-links", action="store_true")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--audit-date", type=str, default=date.today().isoformat())
    p.add_argument("--tickers", type=str, default="")
    return p.parse_args(argv)


def _load_tickers_from_watchlist(root: Path) -> list[str]:
    import yaml
    p = root / "config" / "watchlist.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
    return [item["ticker"] for item in (data.get("watchlist") or [])]


def main(argv: Sequence[str] | None = None) -> int:
    ns = _parse_args(argv if argv is not None else sys.argv[1:])
    tickers = ([t.strip() for t in ns.tickers.split(",") if t.strip()]
               if ns.tickers else _load_tickers_from_watchlist(ns.root))
    cfg = RunnerConfig(
        root=ns.root,
        audit_date=date.fromisoformat(ns.audit_date),
        window_days=ns.window,
        tickers=tickers,
        checks=tuple(s.strip() for s in ns.checks.split(",") if s.strip()),
        skip_replay=ns.skip_replay,
        replay_tickers=tuple(s.strip() for s in ns.replay_tickers.split(",") if s.strip()),
        max_replay_cost_usd=ns.max_replay_cost_usd,
        dry_run=ns.dry_run,
        suffix=ns.suffix,
        check_links=ns.check_links,
        model_profile="economy",
        git_sha=_git_sha(ns.root),
    )
    code, _ = run_audit(cfg)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
