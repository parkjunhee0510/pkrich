from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BudgetGuardConfig:
    mode: str = "shadow"
    daily_cap_usd: float = 0.25
    monthly_cap_usd: float = 5.0
    on_exceed: str = "log_only"
    guarded_profiles: tuple[str, ...] = ("standard", "deep")
    guarded_paths: tuple[str, ...] = (
        "ensemble_deep",
        "ensemble_tie_break",
        "committee_deep",
        "macro_narrative",
        "policy_impact",
    )


@dataclass(frozen=True)
class BudgetGuardDecision:
    mode: str
    path: str
    profile: str
    estimated_incremental_cost_usd: float
    run_cost_so_far_usd: float
    daily_cap_usd: float
    decision: str
    allowed: bool
    would_block: bool
    reason: str

    def to_log_fields(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "path": self.path,
            "profile": self.profile,
            "estimated_incremental_cost_usd": round(self.estimated_incremental_cost_usd, 8),
            "run_cost_so_far_usd": round(self.run_cost_so_far_usd, 8),
            "daily_cap_usd": round(self.daily_cap_usd, 8),
            "decision": self.decision,
            "allowed": self.allowed,
            "would_block": self.would_block,
            "reason": self.reason,
        }


def budget_guard_config_from_mapping(raw: dict[str, Any] | None) -> BudgetGuardConfig:
    raw = raw or {}
    return BudgetGuardConfig(
        mode=_choice(raw.get("mode"), {"off", "shadow", "enforce"}, default="shadow"),
        daily_cap_usd=_float(raw.get("daily_cap_usd"), default=0.25),
        monthly_cap_usd=_float(raw.get("monthly_cap_usd"), default=5.0),
        on_exceed=_choice(
            raw.get("on_exceed"),
            {"log_only", "skip_deep", "economy_only", "abort_optional"},
            default="log_only",
        ),
        guarded_profiles=tuple(_list(raw.get("guarded_profiles"), default=("standard", "deep"))),
        guarded_paths=tuple(
            _list(
                raw.get("guarded_paths"),
                default=("ensemble_deep", "ensemble_tie_break", "committee_deep", "macro_narrative", "policy_impact"),
            )
        ),
    )


def evaluate_budget_guard(
    *,
    config: BudgetGuardConfig,
    path: str,
    profile: str,
    estimated_incremental_cost_usd: float,
    run_cost_so_far_usd: float,
) -> BudgetGuardDecision:
    normalized_mode = config.mode.strip().lower()
    guarded = path in config.guarded_paths and profile in config.guarded_profiles
    cap_exceeded = run_cost_so_far_usd + estimated_incremental_cost_usd > config.daily_cap_usd

    if normalized_mode == "off" or not guarded:
        return _decision(
            config,
            path,
            profile,
            estimated_incremental_cost_usd,
            run_cost_so_far_usd,
            "allow",
            True,
            False,
            "unguarded_or_off",
        )
    if not cap_exceeded:
        return _decision(
            config,
            path,
            profile,
            estimated_incremental_cost_usd,
            run_cost_so_far_usd,
            "allow",
            True,
            False,
            "within_daily_cap",
        )
    if normalized_mode == "shadow":
        return _decision(
            config,
            path,
            profile,
            estimated_incremental_cost_usd,
            run_cost_so_far_usd,
            "would_block",
            True,
            True,
            "daily_cap_would_be_exceeded",
        )
    return _decision(
        config,
        path,
        profile,
        estimated_incremental_cost_usd,
        run_cost_so_far_usd,
        "blocked",
        False,
        True,
        f"daily_cap_exceeded:{config.on_exceed}",
    )


def estimate_profile_call_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    input_cost_per_1m: float,
    output_cost_per_1m: float,
) -> float:
    return round(
        (
            (max(input_tokens, 0) * input_cost_per_1m)
            + (max(output_tokens, 0) * output_cost_per_1m)
        )
        / 1_000_000,
        8,
    )


def _decision(
    config: BudgetGuardConfig,
    path: str,
    profile: str,
    estimated_incremental_cost_usd: float,
    run_cost_so_far_usd: float,
    decision: str,
    allowed: bool,
    would_block: bool,
    reason: str,
) -> BudgetGuardDecision:
    return BudgetGuardDecision(
        mode=config.mode,
        path=path,
        profile=profile,
        estimated_incremental_cost_usd=float(estimated_incremental_cost_usd or 0.0),
        run_cost_so_far_usd=float(run_cost_so_far_usd or 0.0),
        daily_cap_usd=float(config.daily_cap_usd or 0.0),
        decision=decision,
        allowed=allowed,
        would_block=would_block,
        reason=reason,
    )


def _choice(value: Any, allowed: set[str], *, default: str) -> str:
    text = str(value or default).strip().lower()
    return text if text in allowed else default


def _float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _list(value: Any, *, default: tuple[str, ...]) -> list[str]:
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or list(default)
    return list(default)
