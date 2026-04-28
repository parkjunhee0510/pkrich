from __future__ import annotations

from typing import Any, Sequence

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for
from src.eval.replay import LLMReplayClient, ReplayConfig, run_replay


def _action_match_rate(outputs_per_ticker: dict[str, list[dict]]) -> float:
    matches = 0
    total = 0
    for outputs in outputs_per_ticker.values():
        if len(outputs) < 2:
            continue
        actions = [o.get("action") for o in outputs]
        total += 1
        if len(set(actions)) == 1:
            matches += 1
    return (matches / total) if total else 1.0


def _token_jaccard(a: str, b: str) -> float:
    ta = set((a or "").lower().split())
    tb = set((b or "").lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _summary_similarity(outputs_per_ticker: dict[str, list[dict]]) -> float:
    pairwise: list[float] = []
    for outputs in outputs_per_ticker.values():
        if len(outputs) < 2:
            continue
        for i in range(len(outputs)):
            for j in range(i + 1, len(outputs)):
                pairwise.append(_token_jaccard(
                    outputs[i].get("summary") or "",
                    outputs[j].get("summary") or "",
                ))
    return (sum(pairwise) / len(pairwise)) if pairwise else 1.0


class D1SemanticDrift(BaseCheck):
    check_id = "D1"
    dimension = "semantic_drift"

    def __init__(
        self,
        *,
        client: LLMReplayClient,
        replay_tickers: Sequence[str],
        runs_per_ticker: int,
        max_cost_usd: float,
        dry_run: bool,
    ) -> None:
        self.client = client
        self.replay_tickers = tuple(replay_tickers)
        self.runs_per_ticker = runs_per_ticker
        self.max_cost_usd = max_cost_usd
        self.dry_run = dry_run

    def run(self, dataset: Any) -> CheckResult:
        cfg = ReplayConfig(
            tickers=self.replay_tickers,
            runs_per_ticker=self.runs_per_ticker,
            max_cost_usd=self.max_cost_usd,
            dry_run=self.dry_run,
        )
        replay_result = run_replay(client=self.client, config=cfg)
        if self.dry_run:
            return CheckResult(
                check_id="D1",
                severity="info",
                pass_rate=0.0,
                findings=(),
                metrics={"estimated_cost_usd": replay_result.estimated_cost_usd},
                recommendation="Re-run without --dry-run to obtain actual drift measurement.",
            )
        if replay_result.aborted:
            return CheckResult(
                check_id="D1",
                severity="fail",
                pass_rate=0.0,
                findings=(Finding(detail={
                    "abort_reason": replay_result.abort_reason,
                    "actual_cost_usd": replay_result.actual_cost_usd,
                }),),
                metrics={"actual_cost_usd": replay_result.actual_cost_usd},
                recommendation="Increase --max-replay-cost-usd or reduce --replay-tickers.",
            )

        action_match = _action_match_rate(replay_result.outputs)
        sim = _summary_similarity(replay_result.outputs)
        sev_action = severity_for("D1", value=action_match, kind="action_match")
        sev_sim = severity_for("D1", value=sim, kind="embedding_similarity")
        order = {"pass": 0, "info": 0, "warn": 1, "fail": 2}
        sev = max([sev_action, sev_sim], key=lambda x: order[x])
        findings: list[Finding] = []
        for ticker, outputs in replay_result.outputs.items():
            actions = [o.get("action") for o in outputs]
            if len(set(actions)) > 1:
                findings.append(Finding(
                    ticker=ticker, module="d1_replay",
                    detail={"actions_seen": actions,
                            "summaries": [o.get("summary") for o in outputs]},
                ))
        return CheckResult(
            check_id="D1",
            severity=sev,
            pass_rate=min(action_match, sim),
            findings=tuple(findings),
            metrics={"action_match": action_match,
                     "summary_similarity": sim,
                     "actual_cost_usd": replay_result.actual_cost_usd},
            recommendation=(
                "Reduce model temperature, pin seed where supported, or move from "
                "research_note to committee for higher consensus on drifty tickers."
                if sev != "pass" else None
            ),
        )
