"""Active policy events dossier (Plan B).

Maintains a rolling collection of policy events that are still considered
ACTIVE for ticker-scoring purposes. Each pipeline run:

  1. Loads the existing dossier from ``output/data/policy_active_events.json``.
  2. Prunes events whose ``effective_through`` date has passed OR whose age
     since ``first_seen`` exceeds ``MAX_AGE_DAYS``.
  3. Merges newly-discovered events from this run's stage 1 collector,
     preserving the original ``first_seen`` for known ids.
  4. Recomputes ``decay_weight`` for every survivor so downstream scoring
     can apply temporal weighting.
  5. Persists the updated dossier back to disk.

The dossier file format is intentionally a simple array of event dicts so it
diffs cleanly under git and other tools can consume it without importing
the dataclass.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.types import PolicyEvent

# How long an undated event remains in the dossier before being pruned.
MAX_AGE_DAYS = 30
# Half-life (days) used by the exponential decay weight. After 7 days a
# fresh event's weight halves; after 14 days it quarters; ≤ 30 days it's
# ~5%.
HALF_LIFE_DAYS = 7.0
# Schema version for forward-compatible migration of the JSON file.
SCHEMA_VERSION = 1


def decay_weight(age_days: int) -> float:
    """Exponential decay: 1.0 at age 0, 0.5 at half-life, etc. Floored at 0."""
    if age_days <= 0:
        return 1.0
    return max(0.0, 0.5 ** (age_days / HALF_LIFE_DAYS))


def _parse_iso_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def load_dossier(path: str | Path) -> list[dict[str, Any]]:
    """Read the dossier file, returning [] if missing or malformed."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        events = data.get("events") or []
    elif isinstance(data, list):
        events = data
    else:
        events = []
    return [e for e in events if isinstance(e, dict) and e.get("id")]


def prune_expired(
    events: Iterable[dict[str, Any]], today: str
) -> list[dict[str, Any]]:
    """Drop events whose effective_through has passed or first_seen is too old."""
    today_d = _parse_iso_date(today) or datetime.now(timezone.utc).date()
    survivors: list[dict[str, Any]] = []
    for evt in events:
        eff = _parse_iso_date(evt.get("effective_through") or "")
        first = _parse_iso_date(evt.get("first_seen") or "")
        if eff and eff < today_d:
            continue
        if first and (today_d - first).days > MAX_AGE_DAYS:
            continue
        survivors.append(evt)
    return survivors


def merge_new(
    dossier: list[dict[str, Any]],
    new_events: Iterable[PolicyEvent],
    today: str,
) -> list[dict[str, Any]]:
    """Merge ``new_events`` into the dossier, preserving first_seen for known ids."""
    by_id = {evt["id"]: dict(evt) for evt in dossier}
    for ev in new_events:
        ev_dict = asdict(ev)
        prev = by_id.get(ev.id)
        if prev:
            # Re-discovered: keep first_seen, refresh last_seen + dynamic fields.
            prev["last_seen"] = today
            # Refresh effective_through if the new run has a value and the
            # stored one is empty (LLM may improve the estimate over time).
            if ev_dict.get("effective_through") and not prev.get("effective_through"):
                prev["effective_through"] = ev_dict["effective_through"]
            # Always refresh confidence to the latest observation (LLM signal
            # may strengthen as more sources cite the event).
            prev["confidence"] = ev_dict.get("confidence", prev.get("confidence", 0.5))
        else:
            ev_dict["first_seen"] = ev_dict.get("first_seen") or today
            ev_dict["last_seen"] = today
            by_id[ev.id] = ev_dict
    return list(by_id.values())


def apply_decay(
    events: Iterable[dict[str, Any]], today: str
) -> list[dict[str, Any]]:
    """Annotate every event with ``age_days`` and ``decay_weight`` for ``today``."""
    today_d = _parse_iso_date(today) or datetime.now(timezone.utc).date()
    out: list[dict[str, Any]] = []
    for evt in events:
        first = _parse_iso_date(evt.get("first_seen") or "")
        age = (today_d - first).days if first else 0
        if age < 0:
            age = 0
        weight = decay_weight(age)
        annotated = dict(evt)
        annotated["age_days"] = age
        annotated["decay_weight"] = round(weight, 4)
        out.append(annotated)
    # Sort by decay_weight × confidence descending so most-relevant first.
    out.sort(
        key=lambda e: float(e.get("decay_weight", 0.0))
        * float(e.get("confidence", 0.0)),
        reverse=True,
    )
    return out


def write_dossier(events: list[dict[str, Any]], path: str | Path) -> None:
    """Atomically persist the dossier as ``{schema_version, as_of, events}``."""
    p = Path(path)
    if p.parent:
        p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "as_of": _today_iso(),
        "events": events,
    }
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def update_dossier(
    new_events: Iterable[PolicyEvent],
    today: str,
    path: str | Path = "output/data/policy_active_events.json",
) -> list[dict[str, Any]]:
    """End-to-end helper: load → prune → merge → decay → write.

    Returns the up-to-date list of decay-annotated event dicts. Each entry
    carries the original PolicyEvent fields plus ``first_seen``, ``last_seen``,
    ``age_days``, and ``decay_weight``.
    """
    existing = load_dossier(path)
    pruned = prune_expired(existing, today)
    merged = merge_new(pruned, new_events, today)
    decayed = apply_decay(merged, today)
    write_dossier(decayed, path)
    return decayed


def to_policy_events(dossier_entries: Iterable[dict[str, Any]]) -> list[PolicyEvent]:
    """Convert dossier dicts back to PolicyEvent dataclasses for stage 2."""
    out: list[PolicyEvent] = []
    for entry in dossier_entries:
        try:
            out.append(
                PolicyEvent(
                    id=entry["id"],
                    category=entry.get("category", "other"),
                    headline=entry.get("headline", ""),
                    summary=entry.get("summary", ""),
                    raw_excerpt=entry.get("raw_excerpt", ""),
                    source_url=entry.get("source_url", ""),
                    source_domain=entry.get("source_domain", ""),
                    published_at=entry.get("published_at", ""),
                    confidence=float(entry.get("confidence", 0.5)),
                    effective_through=entry.get("effective_through", "") or "",
                    first_seen=entry.get("first_seen", "") or "",
                    last_seen=entry.get("last_seen", "") or "",
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out
