"""Triple-barrier labeling (López de Prado, 2018).

Replaces the "ride the signal for 5 sessions and measure return" convention
with a more honest outcome label that mirrors how a human would trade:

  • **Take-profit (hit)**  — price reaches +TP% in direction of the signal
  • **Stop-loss  (stop)**  — price reaches -SL% against the signal
  • **Timeout   (timeout)** — neither barrier touched within N trading days

The first barrier touched wins. This avoids the asymmetry where a signal
that spikes +20% then drops to -1% on day 5 looks "slightly bad" when it
was actually a huge winner we should have locked in.

Why additive, not a replacement:
  - Existing `return_5d` is referenced by many consumers (admin UI,
    backtest, factor_audit). Replacing it would require a schema sweep.
  - Triple-barrier columns are written alongside — consumers opt in as
    they migrate.

Daily bars are used (price_history `high` / `low` / `close`). Intraday
resolution would be ideal but is unavailable in the free data path; the
daily approximation is conservative: we treat a barrier as "touched" the
first trading day the bar's intraday range crosses it.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

TP_DEFAULT = 0.03  # +3% take-profit
SL_DEFAULT = 0.02  # -2% stop-loss (stored as positive magnitude)
HORIZON_DEFAULT = 20  # trading sessions

BARRIER_FIELDS: tuple[str, ...] = (
    "barrier_label",      # hit | stop | timeout | pending
    "barrier_hit_day",    # 1-indexed trading session number, "" if pending
    "barrier_return",     # realized return at label time, "%+.2f%%"
)

_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def _parse_float(raw: object) -> float | None:
    text = str(raw or "").strip()
    if not text or text == "N/A":
        return None
    match = _NUMBER_PATTERN.search(text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _format_percent(value: float) -> str:
    return f"{value:+.2f}%"


def build_ohlc_series(
    price_history_rows: list[dict[str, str]],
) -> dict[str, list[tuple[date, float, float, float]]]:
    """Group price_history rows by ticker into chronological (date, high, low, close) tuples."""
    by_ticker: dict[str, dict[date, tuple[float, float, float]]] = {}
    for row in price_history_rows:
        ticker = str(row.get("ticker", "")).strip().upper()
        raw_date = str(row.get("date", "")).strip()
        try:
            bar_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        high = _parse_float(row.get("high")) or _parse_float(row.get("price"))
        low = _parse_float(row.get("low")) or _parse_float(row.get("price"))
        close = _parse_float(row.get("close")) or _parse_float(row.get("price"))
        if not ticker or high is None or low is None or close is None:
            continue
        by_ticker.setdefault(ticker, {})[bar_date] = (high, low, close)
    return {
        ticker: [(d, h, l, c) for d, (h, l, c) in sorted(bars.items())]
        for ticker, bars in by_ticker.items()
    }


def label_signal(
    *,
    signal_date: date,
    signal_price: float,
    direction: str,
    sessions: list[tuple[date, float, float, float]],
    tp: float = TP_DEFAULT,
    sl: float = SL_DEFAULT,
    horizon: int = HORIZON_DEFAULT,
) -> dict[str, str] | None:
    """Walk forward day by day, return the first barrier touched.

    Returns None when the signal is still pending (fewer than `horizon`
    future sessions AND no barrier touched yet).

    For `bear` direction the barriers are flipped (profit = price drop).
    `neutral` direction treats both sides symmetrically — the label is
    whichever barrier is touched first, reinterpreted as "mean-reversion"
    (hit = stayed within band through horizon, stop = either side touched).
    """
    forward = [
        session
        for session in sessions
        if session[0] > signal_date
    ][:horizon]
    if not forward:
        return None

    upper = signal_price * (1.0 + tp)
    lower = signal_price * (1.0 - sl)

    for index, (bar_date, high, low, close) in enumerate(forward, start=1):
        hit_upper = high >= upper
        hit_lower = low <= lower
        if direction == "bear":
            # bear signal: profit target is a drop, stop is a rise
            if hit_lower:  # price fell — this is our profit
                return {
                    "barrier_label": "hit",
                    "barrier_hit_day": str(index),
                    "barrier_return": _format_percent(-sl * 100),
                    "barrier_date": bar_date.isoformat(),
                }
            if hit_upper:  # price rose against us — stop
                return {
                    "barrier_label": "stop",
                    "barrier_hit_day": str(index),
                    "barrier_return": _format_percent(tp * 100),
                    "barrier_date": bar_date.isoformat(),
                }
        elif direction == "neutral":
            # neutral: either barrier touched → "stop" (thesis broken)
            if hit_upper or hit_lower:
                touched = upper if hit_upper else lower
                return {
                    "barrier_label": "stop",
                    "barrier_hit_day": str(index),
                    "barrier_return": _format_percent(
                        (touched - signal_price) / signal_price * 100
                    ),
                    "barrier_date": bar_date.isoformat(),
                }
        else:
            # bull (default)
            if hit_upper:
                return {
                    "barrier_label": "hit",
                    "barrier_hit_day": str(index),
                    "barrier_return": _format_percent(tp * 100),
                    "barrier_date": bar_date.isoformat(),
                }
            if hit_lower:
                return {
                    "barrier_label": "stop",
                    "barrier_hit_day": str(index),
                    "barrier_return": _format_percent(-sl * 100),
                    "barrier_date": bar_date.isoformat(),
                }

    # Neither barrier touched within window.
    if len(forward) < horizon:
        return None  # still pending — revisit on next update

    last_bar_date, _, _, last_close = forward[-1]
    timeout_return = (last_close - signal_price) / signal_price * 100
    if direction == "neutral":
        label = "hit"  # stayed within band → mean-reversion thesis held
    else:
        label = "timeout"
    return {
        "barrier_label": label,
        "barrier_hit_day": str(len(forward)),
        "barrier_return": _format_percent(timeout_return),
        "barrier_date": last_bar_date.isoformat(),
    }


def summarize_barrier_outcomes(
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    """Aggregate hit/stop/timeout counts for dashboard reporting."""
    labels = {"hit": 0, "stop": 0, "timeout": 0, "pending": 0}
    returns_by_label: dict[str, list[float]] = {k: [] for k in labels}
    hit_days: list[int] = []

    for row in rows:
        label = str(row.get("barrier_label", "")).strip().lower()
        if label not in labels:
            label = "pending"
        labels[label] += 1
        ret = _parse_float(row.get("barrier_return"))
        if ret is not None:
            returns_by_label[label].append(ret)
        try:
            day = int(row.get("barrier_hit_day", "") or 0)
            if day > 0 and label in {"hit", "stop"}:
                hit_days.append(day)
        except (TypeError, ValueError):
            continue

    total = sum(labels.values())
    resolved = total - labels["pending"]
    hit_rate = (labels["hit"] / resolved) if resolved else None

    summary: dict[str, Any] = {
        "total": total,
        "counts": labels,
        "hit_rate": round(hit_rate, 3) if hit_rate is not None else None,
        "avg_days_to_barrier": (
            round(sum(hit_days) / len(hit_days), 1) if hit_days else None
        ),
        "avg_return_by_label": {
            key: (
                round(sum(values) / len(values), 3) if values else None
            )
            for key, values in returns_by_label.items()
        },
    }
    return summary
