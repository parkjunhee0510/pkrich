from __future__ import annotations

import statistics
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


TRACKED_SIGNALS: tuple[str, ...] = ("narrative_strength", "news_sentiment_score")


class D3SignalVolatility(BaseCheck):
    check_id = "D3"
    dimension = "signal_volatility"

    def run(self, dataset: Any) -> CheckResult:
        per_ticker_signal_std: dict[tuple[str, str], float] = {}
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            samples_by_signal: dict[str, list[float]] = {s: [] for s in TRACKED_SIGNALS}
            for record in days.values():
                signals = (record.get("payload") or {}).get("llm_signals") or {}
                for s in TRACKED_SIGNALS:
                    if s in signals and isinstance(signals[s], (int, float)):
                        samples_by_signal[s].append(float(signals[s]))
            for s, vals in samples_by_signal.items():
                if len(vals) >= 2:
                    std = statistics.pstdev(vals)
                    per_ticker_signal_std[(ticker, s)] = std
                    if std > 0.40:
                        findings.append(Finding(
                            ticker=ticker, jsonpath=f"$.payload.llm_signals.{s}",
                            detail={"std": std, "samples": vals},
                        ))
        worst = max(per_ticker_signal_std.values()) if per_ticker_signal_std else 0.0
        if not per_ticker_signal_std:
            return CheckResult(
                check_id="D3",
                severity="info",
                pass_rate=0.0,
                findings=(Finding(
                    module="payload",
                    jsonpath="$.payload.llm_signals",
                    detail={"reason": "no_signal_samples_evaluated"},
                ),),
                metrics={"worst_signal_std": 0.0, "sample_count": 0.0},
                recommendation="No llm_signals samples were found for volatility measurement.",
            )
        sev = severity_for("D3", value=worst, kind="signal_std")
        return CheckResult(
            check_id="D3",
            severity=sev,
            pass_rate=1.0 - min(worst, 1.0),
            findings=tuple(findings),
            metrics={"worst_signal_std": worst, "sample_count": float(len(per_ticker_signal_std))},
            recommendation=(
                "Inspect LLM signal generation; consider averaging across n committee samples."
                if sev != "pass" else None
            ),
        )
