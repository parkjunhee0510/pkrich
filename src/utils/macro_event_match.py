from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.utils.config import load_yaml_mapping

_DEFAULT_RULES_PATH = "config/macro_event_rules.yaml"


@dataclass(frozen=True)
class IndustryRule:
    tokens: tuple[str, ...]
    score: int
    reason: str


@dataclass(frozen=True)
class MacroEventRules:
    sector_aliases: dict[str, str]
    sector_impacts: dict[str, dict[str, int]]
    industry_rules: dict[str, tuple[IndustryRule, ...]]


def match_macro_events_for_context(
    macro_context: dict[str, Any] | None,
    *,
    sector: str,
    industry: str = "",
    keywords: list[str] | None = None,
    rules_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(macro_context, dict):
        return []
    events = macro_context.get("macro_events", [])
    if not isinstance(events, list):
        return []

    matches: list[dict[str, Any]] = []
    for event in events[:3]:
        if not isinstance(event, dict):
            continue
        impact = score_macro_event_match(
            event,
            sector=sector,
            industry=industry,
            keywords=keywords or [],
            rules_path=rules_path,
        )
        if impact["score"] == 0:
            continue
        matches.append({**event, **impact})
    matches.sort(key=lambda item: abs(int(item.get("score", 0))), reverse=True)
    return matches


def score_macro_event_match(
    event: dict[str, Any],
    *,
    sector: str,
    industry: str = "",
    keywords: list[str] | None = None,
    rules_path: str | Path | None = None,
) -> dict[str, Any]:
    rules = _load_macro_event_rules(rules_path)
    normalized_sector = _normalize_sector_with_rules(sector, rules)
    industry_text = normalize_text(industry)
    keyword_text = " ".join(normalize_text(keyword) for keyword in (keywords or []))
    combined_text = f"{industry_text} {keyword_text}".strip()
    event_type = str(event.get("event_type", "")).strip()

    score = rules.sector_impacts.get(event_type, {}).get(normalized_sector, 0)
    matched_dimension = "sector" if score else ""
    reason = str(event.get("summary_ko", "")).strip()

    for rule in rules.industry_rules.get(event_type, ()):
        if not any(token in combined_text for token in rule.tokens):
            continue
        if abs(rule.score) >= abs(score):
            score = rule.score
            matched_dimension = "industry"
            reason = rule.reason

    return {
        "score": int(score),
        "matched_dimension": matched_dimension or "none",
        "match_reason": reason,
    }


def normalize_sector(raw: str) -> str:
    return _normalize_sector_with_rules(raw, _load_macro_event_rules())


def normalize_text(raw: str) -> str:
    return " ".join(str(raw or "").strip().lower().split())


def _normalize_sector_with_rules(raw: str, rules: MacroEventRules) -> str:
    normalized = normalize_text(raw)
    return rules.sector_aliases.get(normalized, normalized)


def _load_macro_event_rules(rules_path: str | Path | None = None) -> MacroEventRules:
    if rules_path is None:
        return _load_default_macro_event_rules()
    return _parse_macro_event_rules(load_yaml_mapping(str(rules_path)))


@lru_cache(maxsize=1)
def _load_default_macro_event_rules() -> MacroEventRules:
    return _parse_macro_event_rules(load_yaml_mapping(_DEFAULT_RULES_PATH))


def _parse_macro_event_rules(payload: dict[str, Any]) -> MacroEventRules:
    return MacroEventRules(
        sector_aliases=_normalize_sector_aliases(payload.get("sector_aliases", {})),
        sector_impacts=_normalize_sector_impacts(payload.get("sector_impacts", {})),
        industry_rules=_normalize_industry_rules(payload.get("industry_rules", {})),
    )


def _normalize_sector_aliases(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    aliases: dict[str, str] = {}
    for source, target in raw.items():
        source_key = normalize_text(source)
        target_key = normalize_text(target)
        if source_key and target_key:
            aliases[source_key] = target_key
    return aliases


def _normalize_sector_impacts(raw: object) -> dict[str, dict[str, int]]:
    if not isinstance(raw, dict):
        return {}

    impacts: dict[str, dict[str, int]] = {}
    for event_type, sector_scores in raw.items():
        event_key = str(event_type or "").strip()
        if not event_key or not isinstance(sector_scores, dict):
            continue
        normalized_scores: dict[str, int] = {}
        for sector, score in sector_scores.items():
            sector_key = normalize_text(sector)
            if not sector_key:
                continue
            try:
                normalized_scores[sector_key] = int(score)
            except (TypeError, ValueError):
                continue
        if normalized_scores:
            impacts[event_key] = normalized_scores
    return impacts


def _normalize_industry_rules(raw: object) -> dict[str, tuple[IndustryRule, ...]]:
    if not isinstance(raw, dict):
        return {}

    industry_rules: dict[str, tuple[IndustryRule, ...]] = {}
    for event_type, entries in raw.items():
        event_key = str(event_type or "").strip()
        if not event_key or not isinstance(entries, list):
            continue
        normalized_entries = tuple(
            rule for entry in entries if (rule := _normalize_industry_rule(entry)) is not None
        )
        if normalized_entries:
            industry_rules[event_key] = normalized_entries
    return industry_rules


def _normalize_industry_rule(raw: object) -> IndustryRule | None:
    if not isinstance(raw, dict):
        return None

    tokens = _normalize_token_list(raw.get("tokens", []))
    if not tokens:
        return None
    try:
        score = int(raw.get("score", 0))
    except (TypeError, ValueError):
        return None
    reason = str(raw.get("reason", "") or "").strip()
    return IndustryRule(tokens=tokens, score=score, reason=reason)


def _normalize_token_list(raw: object) -> tuple[str, ...]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return ()

    tokens: list[str] = []
    for token in raw:
        normalized = normalize_text(token)
        if normalized:
            tokens.append(normalized)
    return tuple(tokens)
