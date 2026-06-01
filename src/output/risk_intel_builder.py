"""Build deterministic risk intelligence graph artifacts from finalized outputs."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from src.output.risk_intel_config import (
    ALERT_LEVEL_LABEL_KO,
    CONFIDENCE_CONFIG_VERSION,
    EVIDENCE_TYPE_LABEL_KO,
    RISK_INTEL_SCHEMA_VERSION,
    SCORING_CONFIG_VERSION,
    SOURCE_CONFIG_VERSION,
)
from src.output.risk_intel_scoring import (
    alert_level_for_score,
    apply_caps,
    confidence_for_edge,
    evidence_strength,
    raw_score,
)
from src.types import PortfolioSummary, WatchlistItem


def build_risk_intel_artifacts(
    *,
    run_date: date,
    policy_payload: dict[str, Any] | None,
    search_evidence_payload: dict[str, Any] | None,
    watchlist: list[WatchlistItem],
    portfolio_summary: PortfolioSummary | None,
    sector_payload: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    as_of = run_date.isoformat()
    run_id = f"run:{as_of}-risk-intel"
    generation = {
        "run_id": run_id,
        "as_of": as_of,
        "scoring_config_version": SCORING_CONFIG_VERSION,
        "confidence_config_version": CONFIDENCE_CONFIG_VERSION,
        "source_config_version": SOURCE_CONFIG_VERSION,
        "generated_at": datetime.combine(run_date, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
    }
    input_status = _input_status(
        policy_payload,
        search_evidence_payload,
        watchlist,
        portfolio_summary,
        sector_payload,
        as_of,
    )
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    source_records: dict[str, dict[str, Any]] = {}
    domain_rules: dict[str, dict[str, Any]] = {}
    held_tickers = _held_tickers(portfolio_summary)
    watchlist_by_ticker = {item.ticker.upper(): item for item in watchlist}
    sector_by_ticker = _sector_by_ticker(watchlist, sector_payload)

    alert_paths: list[dict[str, Any]] = []
    if policy_payload:
        for event in policy_payload.get("events", []) or []:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id", "")).strip()
            if not event_id:
                continue
            issue_id = f"issue:{_slug(event.get('category') or event.get('headline') or event_id)}:{event_id}"
            _add_node(
                nodes,
                issue_id,
                "issue",
                str(event.get("headline") or event_id),
                str(event.get("summary") or "정책 이슈가 관찰됐습니다."),
                as_of,
            )
            record_id = f"record:policy:{event_id}"
            source_records[record_id] = _source_record_from_event(record_id, event, as_of)
            impacts = policy_payload.get("impacts_by_event", {}).get(event_id, [])
            for impact in impacts if isinstance(impacts, list) else []:
                if not isinstance(impact, dict):
                    continue
                ticker = str(impact.get("ticker", "")).strip().upper()
                if not ticker:
                    continue
                ticker_node_id = f"ticker:{ticker}"
                sector_id = sector_by_ticker.get(
                    ticker,
                    _slug(getattr(watchlist_by_ticker.get(ticker), "sector", "") or "unknown"),
                )
                sector_node_id = f"sector:{sector_id}"
                _add_node(nodes, sector_node_id, "sector", sector_id, _sector_label_ko(sector_id), as_of)
                _add_node(nodes, ticker_node_id, "ticker", ticker, ticker, as_of)
                rule_id = f"rule:{_slug(event.get('category') or 'policy')}:{sector_id}:v1"
                domain_rules.setdefault(rule_id, _domain_rule(rule_id, event, sector_id, as_of))

                inferred_edge_id = f"edge:{issue_id}:{sector_node_id}"
                edges.setdefault(
                    inferred_edge_id,
                    _edge(
                        edge_id=inferred_edge_id,
                        source_id=issue_id,
                        target_id=sector_node_id,
                        relationship="inferred_affects",
                        evidence_type="inferred",
                        confidence=confidence_for_edge("inferred", "high"),
                        severity_delta=_severity_delta(impact),
                        evidence_refs=[record_id],
                        inference_refs=[rule_id],
                        explanation_ko=str(
                            impact.get("rationale")
                            or "정책 이슈가 섹터 리스크로 전파될 수 있습니다."
                        ),
                        as_of=as_of,
                    ),
                )
                exposure_edge_id = f"edge:{sector_node_id}:{ticker_node_id}"
                edges.setdefault(
                    exposure_edge_id,
                    _edge(
                        edge_id=exposure_edge_id,
                        source_id=sector_node_id,
                        target_id=ticker_node_id,
                        relationship="exposes",
                        evidence_type="explicit",
                        confidence=confidence_for_edge("explicit", "direct"),
                        severity_delta=_severity_delta(impact),
                        evidence_refs=[record_id],
                        inference_refs=[],
                        explanation_ko=f"{ticker}는 {sector_id} 섹터 노출로 연결됩니다.",
                        as_of=as_of,
                    ),
                )
                alert_paths.append(
                    _alert_path(
                        run_date=as_of,
                        issue_id=issue_id,
                        sector_id=sector_node_id,
                        ticker_id=ticker_node_id,
                        impact=impact,
                        record_id=record_id,
                        edge_ids=[inferred_edge_id, exposure_edge_id],
                        edge_types=["inferred", "explicit"],
                        inference_refs=[rule_id],
                        held=ticker in held_tickers,
                        watchlist=ticker in watchlist_by_ticker,
                        source_records=[source_records[record_id]],
                    )
                )

    alert_paths = _dedupe_alert_paths(alert_paths)
    pending_duplicate_candidates: list[dict[str, Any]] = []
    health_warnings = _health_warnings(
        input_status=input_status,
        pending_duplicate_candidates=pending_duplicate_candidates,
        domain_rules=domain_rules,
        alert_paths=alert_paths,
        as_of=as_of,
    )
    status = _status_from_inputs(input_status, alert_paths, domain_rules, health_warnings)
    graph = {
        "schema_version": RISK_INTEL_SCHEMA_VERSION,
        "as_of": as_of,
        "status": status,
        "nodes": sorted(nodes.values(), key=lambda item: item["id"]),
        "edges": sorted(edges.values(), key=lambda item: item["id"]),
        "alert_paths": alert_paths,
        "source_records": sorted(source_records.values(), key=lambda item: item["id"]),
        "domain_rules": sorted(domain_rules.values(), key=lambda item: item["id"]),
        "required_inputs": _required_inputs(),
        "input_status": input_status,
        "pending_duplicate_candidates": pending_duplicate_candidates,
        "health_warnings": health_warnings,
        "summary": {"alert_path_count": len(alert_paths)},
        "generation": generation,
    }
    summary = _summary_from_graph(graph)
    refresh_log = _refresh_log(as_of, status, generation)
    return {"graph": graph, "summary": summary, "refresh_log": refresh_log}


def _slug(value: object) -> str:
    text = str(value or "unknown").strip().lower()
    text = re.sub(r"[^a-z0-9가-힣]+", "-", text)
    return text.strip("-") or "unknown"


def _required_inputs() -> dict[str, list[str]]:
    return {
        "tier1_required": [
            "output/data/policy_impact.json",
            "output/data/search_evidence.json",
            "output/data/portfolio.json",
            "output/data/watchlist.json",
            "output/data/sector_exposure.json",
        ],
        "tier1_optional": [
            "output/data/market_reaction.json",
            "output/data/macro.json",
            "output/data/performance_telemetry.json",
            "config/sectors.yaml",
            "output/data/sectors.json",
        ],
    }


def _input_status(
    policy_payload: dict[str, Any] | None,
    search_evidence_payload: dict[str, Any] | None,
    watchlist: list[WatchlistItem],
    portfolio_summary: PortfolioSummary | None,
    sector_payload: dict[str, Any] | None,
    as_of: str,
) -> list[dict[str, object]]:
    return [
        _status_row(
            "policy_impact",
            "output/data/policy_impact.json",
            policy_payload is not None,
            len((policy_payload or {}).get("events", []) or []),
            True,
            as_of,
        ),
        _status_row(
            "search_evidence",
            "output/data/search_evidence.json",
            search_evidence_payload is not None,
            len((search_evidence_payload or {}).get("items", []) or []),
            True,
            as_of,
        ),
        _status_row(
            "portfolio",
            "output/data/portfolio.json",
            portfolio_summary is not None,
            len(getattr(portfolio_summary, "positions", []) or []),
            True,
            as_of,
        ),
        _status_row("watchlist", "output/data/watchlist.json", bool(watchlist), len(watchlist), True, as_of),
        _status_row(
            "sector_exposure",
            "output/data/sector_exposure.json",
            sector_payload is not None,
            len((sector_payload or {}).get("sectors", []) or []),
            True,
            as_of,
        ),
        {
            "name": "social_signals",
            "tier": 3,
            "required": False,
            "status": "skipped_not_enabled",
            "record_count": 0,
        },
    ]


def _status_row(name: str, path: str, present: bool, count: int, required: bool, as_of: str) -> dict[str, object]:
    return {
        "name": name,
        "path": path,
        "tier": 1,
        "required": required,
        "status": "present" if present else "missing",
        "record_count": int(count) if present else 0,
        "as_of": as_of,
    }


def _held_tickers(portfolio_summary: PortfolioSummary | None) -> set[str]:
    positions = getattr(portfolio_summary, "positions", None) or []
    return {str(position.ticker).upper() for position in positions if str(position.ticker).strip()}


def _sector_by_ticker(watchlist: list[WatchlistItem], sector_payload: dict[str, Any] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in watchlist:
        if item.sector:
            mapping[item.ticker.upper()] = _slug(item.sector)
    for sector in (sector_payload or {}).get("sectors", []) or []:
        if not isinstance(sector, dict):
            continue
        sector_id = _slug(sector.get("id") or sector.get("name") or "unknown")
        for row in sector.get("tickers", []) or []:
            if isinstance(row, dict):
                ticker = str(row.get("ticker", "")).strip().upper()
            else:
                ticker = str(row).strip().upper()
            if ticker:
                mapping[ticker] = sector_id
    return mapping


def _sector_label_ko(sector_id: str) -> str:
    return sector_id.replace("-", " ").replace("_", " ")


def _add_node(
    nodes: dict[str, dict[str, Any]],
    node_id: str,
    node_type: str,
    label: str,
    summary_ko: str,
    as_of: str,
) -> None:
    nodes.setdefault(
        node_id,
        {
            "id": node_id,
            "canonical_id": node_id,
            "aliases": [],
            "node_type": node_type,
            "label": label,
            "label_ko": label if node_type == "ticker" else summary_ko[:40],
            "summary_ko": summary_ko,
            "status": "active",
            "first_seen": as_of,
            "last_seen": as_of,
        },
    )


def _source_record_from_event(record_id: str, event: dict[str, Any], as_of: str) -> dict[str, Any]:
    domain = str(event.get("source_domain", "")).lower()
    official = domain.endswith(".gov") or "gov" in domain
    return {
        "id": record_id,
        "source_type": "policy_document" if official else "reputable_news",
        "title": str(event.get("headline") or record_id),
        "title_ko": str(event.get("headline") or record_id),
        "url": str(event.get("source_url") or ""),
        "published_at": str(event.get("published_at") or as_of),
        "trust_tier": "official" if official else "reputable_news",
        "summary_ko": str(event.get("summary") or "정책 이슈 근거입니다."),
    }


def _domain_rule(rule_id: str, event: dict[str, Any], sector_id: str, as_of: str) -> dict[str, Any]:
    category = str(event.get("category") or "policy")
    return {
        "id": rule_id,
        "version": as_of,
        "source_type": "internal_domain_map",
        "title": f"{category} can affect {sector_id}",
        "title_ko": f"{category} 이슈는 {sector_id} 섹터에 영향을 줄 수 있음",
        "rationale_ko": f"정책 이벤트와 {sector_id} 섹터 노출 관계를 내부 도메인 룰로 연결합니다.",
        "rule_confidence": 0.75,
        "last_reviewed": as_of,
    }


def _edge(
    *,
    edge_id: str,
    source_id: str,
    target_id: str,
    relationship: str,
    evidence_type: str,
    confidence: float,
    severity_delta: float,
    evidence_refs: list[str],
    inference_refs: list[str],
    explanation_ko: str,
    as_of: str,
) -> dict[str, Any]:
    return {
        "id": edge_id,
        "source_id": source_id,
        "target_id": target_id,
        "relationship": relationship,
        "relationship_label_ko": "영향 가능" if relationship == "inferred_affects" else "노출",
        "evidence_type": evidence_type,
        "evidence_label_ko": EVIDENCE_TYPE_LABEL_KO[evidence_type],
        "confidence": round(float(confidence), 4),
        "severity_delta": severity_delta,
        "evidence_refs": evidence_refs,
        "inference_refs": inference_refs,
        "explanation_ko": explanation_ko,
        "created_at": f"{as_of}T00:00:00+09:00",
        "updated_at": f"{as_of}T00:00:00+09:00",
    }


def _severity_delta(impact: dict[str, Any]) -> float:
    score = impact.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        direction = str(impact.get("direction", "")).lower()
        score = -0.30 if direction == "negative" else 0.30 if direction == "positive" else 0.0
    return max(-1.0, min(1.0, float(score)))


def _alert_path(
    *,
    run_date: str,
    issue_id: str,
    sector_id: str,
    ticker_id: str,
    impact: dict[str, Any],
    record_id: str,
    edge_ids: list[str],
    edge_types: list[str],
    inference_refs: list[str],
    held: bool,
    watchlist: bool,
    source_records: list[dict[str, Any]],
) -> dict[str, Any]:
    ticker = ticker_id.split(":", 1)[1]
    severity_delta = _severity_delta(impact)
    relationship_confidence = max(0.0, min(1.0, float(impact.get("confidence", 0.65) or 0.65)))
    exposure_score = 1.00 if held else 0.75 if watchlist else 0.35
    direct = str(impact.get("strength", "")).lower() == "direct"
    score_breakdown = {
        "evidence_strength": evidence_strength(source_records),
        "proximity_score": 0.68 if direct else 0.55,
        "exposure_score": exposure_score,
        "market_confirmation_score": 0.50 if direct else 0.00,
        "downside_severity_score": round(max(0.0, -severity_delta) * relationship_confidence, 4),
        "social_momentum_score": 0.00,
        "freshness_score": 1.00,
    }
    caps_applied: list[str] = []
    if set(edge_types) == {"inferred"}:
        caps_applied.append("inference_only_cap")
    if source_records and all(record.get("trust_tier") in {"low_quality", "unknown"} for record in source_records):
        caps_applied.append("single_low_quality_source_cap")
    score_result = apply_caps(raw_score(score_breakdown), caps_applied)
    alert_level = alert_level_for_score(float(score_result["score"]))
    return {
        "id": f"alert:{issue_id.split(':')[-1]}:{ticker}:{run_date}",
        "canonical_issue_id": issue_id,
        "target_group_type": "ticker",
        "target_group_id": ticker_id,
        "alert_level": alert_level,
        "alert_level_label_ko": ALERT_LEVEL_LABEL_KO[alert_level],
        "path_node_ids": [issue_id, sector_id, ticker_id],
        "path_edge_ids": edge_ids,
        "edge_evidence_types": edge_types,
        "inference_refs": inference_refs,
        "affected_sector_ids": [sector_id],
        "affected_ticker_ids": [ticker_id],
        "affected_ticker_details": [
            {
                "ticker": ticker,
                "exposure_type": "holding" if held else "watchlist" if watchlist else "sector",
                "exposure_label_ko": "보유" if held else "관심" if watchlist else "섹터",
                "is_holding": held,
            }
        ],
        "representative_target_id": ticker_id,
        **score_result,
        "score_breakdown": score_breakdown,
        "caps_applied": caps_applied,
        "guardrails_applied": ["alert_requires_evidence_refs"] if alert_level == "alert" else [],
        "aggregation": {"method": "max", "candidate_path_count": 1},
        "evidence_counts": {"explicit": 1, "inferred": 1, "social": 0, "market": 0},
        "top_evidence_refs": [record_id],
        "rationale_ko": str(
            impact.get("rationale") or "정책 이슈가 섹터와 종목으로 연결되어 주의가 필요합니다."
        ),
    }


def _dedupe_alert_paths(paths: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[object, tuple[object, ...], tuple[object, ...]], dict[str, Any]] = {}
    for path in paths:
        key = (
            path.get("canonical_issue_id"),
            tuple(sorted(path.get("affected_sector_ids", []))),
            tuple(sorted(path.get("affected_ticker_ids", []))),
        )
        current = deduped.get(key)
        if current is None or float(path.get("score", 0.0)) > float(current.get("score", 0.0)):
            deduped[key] = path
    level_rank = {"alert": 0, "warning": 1, "observation": 2}
    return sorted(
        deduped.values(),
        key=lambda item: (
            level_rank.get(str(item.get("alert_level")), 99),
            -float(item.get("score", 0.0)),
            -float(item.get("score_breakdown", {}).get("freshness_score", 0.0)),
            str(item.get("representative_target_id", "")),
        ),
    )


def _status_from_inputs(
    input_status: list[dict[str, object]],
    alert_paths: list[dict[str, Any]],
    domain_rules: dict[str, dict[str, Any]],
    health_warnings: list[dict[str, Any]],
) -> str:
    _ = (alert_paths, domain_rules)
    required = [row for row in input_status if row.get("required")]
    missing_required = [row for row in required if row.get("status") != "present"]
    optional_not_ok = [row for row in input_status if not row.get("required") and row.get("status") != "present"]
    if required and len(missing_required) / len(required) >= 0.50:
        return "error"
    if missing_required:
        return "degraded"
    if any(row.get("code") == "stale_domain_rule_promoted" for row in health_warnings):
        return "degraded"
    if optional_not_ok:
        return "partial"
    return "ok"


def _health_warnings(
    *,
    input_status: list[dict[str, object]],
    pending_duplicate_candidates: list[dict[str, Any]],
    domain_rules: dict[str, dict[str, Any]],
    alert_paths: list[dict[str, Any]],
    as_of: str,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for row in input_status:
        if row.get("status") in {"cache_only", "stale"}:
            warnings.append(
                {
                    "code": f"input_{row['status']}",
                    "severity": "warning",
                    "message_ko": f"{row.get('name', '입력')} 입력 상태가 {row['status']}입니다.",
                    "ref_type": "input_status",
                    "ref_id": str(row.get("name", "")),
                    "created_at": f"{as_of}T00:00:00+09:00",
                }
            )
    for candidate in pending_duplicate_candidates:
        warnings.append(
            {
                "code": "pending_duplicate_candidate",
                "severity": "info",
                "message_ko": "중복 후보 노드가 수동 검토를 기다리고 있습니다.",
                "ref_type": "pending_duplicate_candidate",
                "ref_id": str(candidate.get("new_candidate_id", "")),
                "created_at": f"{as_of}T00:00:00+09:00",
            }
        )
    promoted_refs = {
        ref
        for path in alert_paths
        if path.get("alert_level") != "observation"
        for ref in path.get("inference_refs", [])
    }
    all_path_refs = {ref for path in alert_paths for ref in path.get("inference_refs", [])}
    for rule_id, rule in domain_rules.items():
        if not _is_stale_rule(rule, as_of):
            continue
        promoted = rule_id in promoted_refs
        warnings.append(
            {
                "code": "stale_domain_rule_promoted" if promoted else "stale_domain_rule",
                "severity": "warning",
                "message_ko": (
                    "오래된 도메인 룰이 리스크 경로에 사용됐습니다."
                    if rule_id in all_path_refs
                    else "오래된 도메인 룰이 검토 대상입니다."
                ),
                "ref_type": "domain_rule",
                "ref_id": rule_id,
                "created_at": f"{as_of}T00:00:00+09:00",
            }
        )
    return warnings


def _is_stale_rule(rule: dict[str, Any], as_of: str) -> bool:
    try:
        reviewed = date.fromisoformat(str(rule.get("last_reviewed", ""))[:10])
        current = date.fromisoformat(as_of[:10])
    except ValueError:
        return True
    return (current - reviewed).days > 365


def build_risk_intel_summary_from_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Build the dashboard-facing summary from a finalized graph contract."""
    return _summary_from_graph(graph)


def build_risk_intel_refresh_log_from_graph(
    graph: dict[str, Any],
    *,
    refresh_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the refresh-log contract from a finalized graph and optional DB refresh rows."""
    payload = _refresh_log(str(graph["as_of"]), str(graph["status"]), dict(graph["generation"]))
    runs = refresh_runs or []
    payload["runs"] = runs
    payload["latest"] = runs[0] if runs else None
    payload["counters"]["generated_patch_count"] = sum(
        1 for row in runs if row.get("patch_status") == "pending"
    )
    return payload


def _summary_from_graph(graph: dict[str, Any]) -> dict[str, Any]:
    node_labels = {
        str(node.get("id")): str(node.get("label_ko") or node.get("label") or node.get("id"))
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("id")
    }
    cards = []
    for path in graph.get("alert_paths", [])[:5]:
        target = str(path.get("representative_target_id", "")).replace("ticker:", "")
        canonical_issue_id = str(path.get("canonical_issue_id", ""))
        issue_label = _issue_category_label(canonical_issue_id) or node_labels.get(canonical_issue_id, canonical_issue_id or "이슈")
        short_issue_label = _truncate_label(issue_label, 44)
        cards.append(
            {
                "id": path["id"],
                "alert_level": path["alert_level"],
                "alert_level_label_ko": path["alert_level_label_ko"],
                "title_ko": f"{path['alert_level_label_ko']}: {target} - {short_issue_label}",
                "summary_ko": path["rationale_ko"],
                "affected_sectors": path.get("affected_sector_ids", []),
                "affected_tickers": path.get("affected_ticker_details", []),
                "evidence_counts": path.get("evidence_counts", {}),
                "top_evidence_refs": path.get("top_evidence_refs", []),
                "rationale_ko": path["rationale_ko"],
                "detail_node_id": canonical_issue_id,
                "score": path.get("score"),
                "raw_score": path.get("raw_score"),
                "score_kind": path.get("score_kind"),
                "cap_value": path.get("cap_value"),
                "caps_applied": path.get("caps_applied", []),
                "guardrails_applied": path.get("guardrails_applied", []),
            }
        )
    return {
        "schema_version": graph["schema_version"],
        "as_of": graph["as_of"],
        "status": graph["status"],
        "cards": cards,
        "counts": {"cards": len(cards), "alert_paths": len(graph.get("alert_paths", []))},
        "source_tier_status": {"tier2": "skipped_not_enabled", "tier3": "skipped_not_enabled"},
        "empty_states": {"ko": "표시할 리스크 경로가 없습니다."},
        "generation": graph["generation"],
        "derived_from_graph_run_id": graph["generation"]["run_id"],
    }


def _issue_category_label(issue_id: str) -> str:
    category = issue_id.split(":")[1] if ":" in issue_id else issue_id
    labels = {
        "antitrust": "반독점",
        "chips-act": "반도체 정책",
        "energy-policy": "에너지 정책",
        "export-control": "수출통제",
        "fda": "식품·의료 규제",
        "sanctions": "제재",
        "tariff": "관세",
    }
    return labels.get(category, "")


def _truncate_label(value: str, max_chars: int) -> str:
    value = value.strip()
    if len(value) <= max_chars:
        return value
    return f"{value[: max_chars - 3].rstrip()}..."


def _refresh_log(as_of: str, status: str, generation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RISK_INTEL_SCHEMA_VERSION,
        "as_of": as_of,
        "status": status,
        "daily_limit": 0,
        "used_today": 0,
        "runs": [],
        "latest": None,
        "counters": {
            "provider_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "provider_errors": 0,
            "generated_patch_count": 0,
        },
        "generation": generation,
        "reset_timezone": "Asia/Seoul",
        "reset_at_local": f"{as_of}T00:00:00+09:00",
    }
