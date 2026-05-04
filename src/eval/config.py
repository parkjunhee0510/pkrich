from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DEFAULT_WINDOW_DAYS: int = 14
DEFAULT_RUNS_PER_TICKER: int = 3
DEFAULT_MAX_REPLAY_COST_USD: float = 1.0
DEFAULT_REPLAY_TICKERS: tuple[str, ...] = ("AAPL", "MSFT", "NVDA", "TSLA", "GOOGL")
ALL_CHECK_IDS: tuple[str, ...] = (
    "I1", "I2", "I3", "I4",
    "O1", "O2", "O3", "O4", "O5",
    "D1", "D2", "D3",
    "R1", "R2", "R3",
)


@dataclass(frozen=True)
class Thresholds:
    pass_at: float
    warn_at: float
    direction: Literal["lower_is_better", "higher_is_better"]


DEFAULT_THRESHOLDS: dict[str, dict[str, Thresholds]] = {
    "I1": {"missing_field_rate": Thresholds(0.02, 0.10, "lower_is_better")},
    "I2": {"missingness_rate": Thresholds(0.30, 0.60, "lower_is_better")},
    "I3": {"format_count": Thresholds(1, 2, "lower_is_better")},
    "I4": {"cv": Thresholds(0.20, 0.40, "lower_is_better")},
    "O1": {"violation_rate": Thresholds(0.0, 0.0, "lower_is_better")},
    "O2": {"match_rate": Thresholds(0.95, 0.85, "higher_is_better")},
    "O3": {"citation_match_rate": Thresholds(0.98, 0.90, "higher_is_better")},
    "O4": {"lang_ratio_std": Thresholds(0.15, 0.30, "lower_is_better")},
    "O5": {"three_way_agreement": Thresholds(0.85, 0.70, "higher_is_better")},
    "D1": {"action_match": Thresholds(1.0, 0.67, "higher_is_better"),
           "embedding_similarity": Thresholds(0.90, 0.80, "higher_is_better")},
    "D2": {"role_agreement": Thresholds(0.75, 0.60, "higher_is_better")},
    "D3": {"signal_std": Thresholds(0.25, 0.40, "lower_is_better")},
    "R1": {"fallback_rate": Thresholds(0.05, 0.15, "lower_is_better")},
    "R2": {"retry_per_ticker": Thresholds(2, 5, "lower_is_better")},
    "R3": {"mismatch_count": Thresholds(0, 0, "lower_is_better")},
}


def severity_for(check_id: str, *, value: float, kind: str) -> str:
    t = DEFAULT_THRESHOLDS[check_id][kind]
    if t.direction == "lower_is_better":
        if value <= t.pass_at:
            return "pass"
        if value <= t.warn_at:
            return "warn"
        return "fail"
    if value >= t.pass_at:
        return "pass"
    if value >= t.warn_at:
        return "warn"
    return "fail"
