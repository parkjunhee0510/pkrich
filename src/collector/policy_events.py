"""Stage 1 of the policy/regulation impact pipeline.

Calls the OpenAI Responses API with the ``web_search`` tool to extract policy
events published in the last 24 hours, applies confidence filters, and
maintains a 7-day cache of seen event IDs.

Pure-data helpers (``filter_events``, ``hash_event_id``, cache I/O) live
alongside the side-effecting ``_openai_web_search`` so unit tests can mock the
external call.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

from src.types import POLICY_CATEGORIES, PolicyEvent


def hash_event_id(headline: str, url: str, published_at: str) -> str:
    raw = f"{headline}|{url}|{published_at}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _matches_domain(domain: str, candidates: list[str]) -> bool:
    return any(domain == c or domain.endswith("." + c) for c in candidates)


def filter_events(
    raw: list[dict],
    today: str,
    trusted: list[str],
    penalized: list[str],
    trust_bonus: float,
    penalty: float,
) -> list[PolicyEvent]:
    today_dt = _parse_iso(today + "T00:00:00Z")
    cutoff = today_dt - timedelta(hours=24)
    out: list[PolicyEvent] = []
    seen: dict[str, PolicyEvent] = {}

    for ev in raw:
        url = (ev.get("source_url") or "").strip()
        if not url:
            continue

        published_at = ev.get("published_at") or ""
        try:
            pub = _parse_iso(published_at)
        except (ValueError, AttributeError):
            continue
        if pub < cutoff:
            continue

        domain = _domain(url)
        confidence = float(ev.get("confidence", 0.5))
        if _matches_domain(domain, trusted):
            confidence = min(1.0, confidence + trust_bonus)
        if _matches_domain(domain, penalized):
            confidence = max(0.0, confidence - penalty)

        category = ev.get("category") or "other"
        if category not in POLICY_CATEGORIES:
            category = "other"

        headline = ev.get("headline", "").strip()
        if not headline:
            continue

        evt_id = hash_event_id(headline, url, published_at)
        if evt_id in seen:
            continue

        event = PolicyEvent(
            id=evt_id,
            category=category,
            headline=headline,
            summary=(ev.get("summary") or "")[:1200],
            raw_excerpt=(ev.get("raw_excerpt") or "")[:4000],
            source_url=url,
            source_domain=domain,
            published_at=published_at,
            confidence=round(confidence, 3),
        )
        seen[evt_id] = event
        out.append(event)

    return out


def load_cache(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(path: str, data: dict) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def prune_cache(cache: dict, today: str, days: int = 7) -> dict:
    today_dt = _parse_iso(today + "T00:00:00Z")
    cutoff = today_dt - timedelta(days=days)
    keep: dict[str, str] = {}
    for key, iso in cache.items():
        try:
            stamp = _parse_iso(str(iso) + "T00:00:00Z" if "T" not in str(iso) else str(iso))
        except (ValueError, AttributeError):
            continue
        if stamp >= cutoff:
            keep[key] = str(iso)[:10]
    return keep


def _openai_web_search(today: str, model_profile: str) -> list[dict]:
    """Real web_search call. Mocked in unit tests."""
    from openai import OpenAI

    from src.utils.config import load_yaml_mapping

    client = OpenAI()
    models_cfg = load_yaml_mapping("config/models.yaml", optional=True) or {}
    profile = (models_cfg.get("profiles") or {}).get(model_profile) or {}
    model = profile.get("model", "gpt-5.4")

    schema = {
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "headline": {"type": "string"},
                        "summary": {"type": "string"},
                        "raw_excerpt": {"type": "string"},
                        "source_url": {"type": "string"},
                        "published_at": {"type": "string"},
                        "category": {
                            "type": "string",
                            "enum": list(POLICY_CATEGORIES),
                        },
                        "confidence": {"type": "number"},
                    },
                    "required": [
                        "headline", "summary", "source_url",
                        "published_at", "category", "confidence",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["events"],
        "additionalProperties": False,
    }

    prompt = (
        f"Find US and global policy/regulation events published in the 24 hours "
        f"before {today}. Cover all of these categories: "
        f"{', '.join(POLICY_CATEGORIES)}. Each event MUST include source_url and "
        "published_at (ISO8601). summary must be ≤ 120 tokens. Return JSON "
        "matching the provided schema."
    )

    response = client.responses.create(
        model=model,
        tools=[{"type": "web_search"}],
        input=prompt,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "policy_events",
                "schema": schema,
                "strict": True,
            },
        },
    )
    payload = json.loads(response.output_text)
    return payload.get("events", []) or []


def extract_events(
    today: str,
    model_profile: str,
    sources_config: dict,
    cache_path: str = "output/data/policy_events_cache.json",
) -> list[PolicyEvent]:
    raw = _openai_web_search(today, model_profile)
    events = filter_events(
        raw,
        today=today,
        trusted=list(sources_config.get("trusted_domains") or []),
        penalized=list(sources_config.get("penalized_domains") or []),
        trust_bonus=float(sources_config.get("trust_bonus", 0.2)),
        penalty=float(sources_config.get("penalty", 0.3)),
    )

    cache = prune_cache(load_cache(cache_path), today=today, days=7)
    for event in events:
        cache.setdefault(event.id, today)
    save_cache(cache_path, cache)

    return events
