from __future__ import annotations

from src.types import TickerAnalysis


def send_daily_summary(_: list[TickerAnalysis]) -> None:
    """Optional Slack delivery hook. Core pipeline should not depend on it."""
    return None
