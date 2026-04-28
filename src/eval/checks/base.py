from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Mapping


Severity = Literal["pass", "warn", "fail", "info"]


@dataclass(frozen=True)
class Finding:
    ticker: str | None = None
    date: date | None = None
    module: str | None = None
    jsonpath: str | None = None
    detail: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.detail is None:
            object.__setattr__(self, "detail", {})


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    severity: Severity
    pass_rate: float
    findings: tuple[Finding, ...]
    metrics: Mapping[str, float]
    recommendation: str | None


class BaseCheck(ABC):
    check_id: str = ""
    dimension: str = ""

    @abstractmethod
    def run(self, dataset: "AuditDataset") -> CheckResult:  # noqa: F821
        raise NotImplementedError
