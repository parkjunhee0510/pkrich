"""Risk intelligence graph constants and display labels."""

from __future__ import annotations

RISK_INTEL_SCHEMA_VERSION = "1.0.0"
SCORING_CONFIG_VERSION = "risk-intel-scoring-v1"
CONFIDENCE_CONFIG_VERSION = "risk-intel-confidence-v1"
SOURCE_CONFIG_VERSION = "risk-intel-source-v1"

ALERT_LEVELS = ("observation", "warning", "alert")
ARTIFACT_STATUSES = ("ok", "partial", "degraded", "error")
NODE_TYPES = ("issue", "policy", "security", "social", "region", "sector", "ticker", "source")
EVIDENCE_TYPES = ("explicit", "inferred", "social", "market")
SOURCE_TYPES = (
    "policy_document",
    "regulator_page",
    "government_page",
    "company_filing",
    "company_ir",
    "sec_document",
    "reputable_news",
    "search_result",
    "domain_rule",
    "market_reaction",
    "social_cluster",
)
RELATIONSHIPS = (
    "mentions",
    "affects",
    "inferred_affects",
    "reacts_to",
    "exposes",
    "corroborates",
)
INPUT_STATUSES = ("present", "missing", "skipped_not_enabled", "provider_error", "cache_only", "stale")
DUPLICATE_STATUSES = ("pending", "merged", "rejected", "expired")
REACTION_STRENGTHS = ("strong", "moderate", "weak", "none")

ALERT_LEVEL_LABEL_KO = {
    "observation": "관찰",
    "warning": "주의",
    "alert": "경보",
}

EVIDENCE_TYPE_LABEL_KO = {
    "explicit": "명시 근거",
    "inferred": "도메인 추론",
    "social": "소셜 신호",
    "market": "시장 확인",
}

NODE_TYPE_LABEL_KO = {
    "issue": "이슈",
    "policy": "정책",
    "security": "안보",
    "social": "소셜",
    "region": "지역",
    "sector": "섹터",
    "ticker": "종목",
    "source": "출처",
}

TRUST_TIER_SCORES = {
    "official": 0.90,
    "filing": 0.85,
    "reputable_news": 0.75,
    "approved_search": 0.65,
    "domain_rule": 0.45,
    "market_data": 0.70,
    "social": 0.30,
    "low_quality": 0.20,
    "unknown": 0.20,
}

SCORE_WEIGHTS = {
    "evidence_strength": 0.30,
    "proximity_score": 0.20,
    "exposure_score": 0.20,
    "market_confirmation_score": 0.15,
    "downside_severity_score": 0.10,
    "social_momentum_score": 0.03,
    "freshness_score": 0.02,
}

CAP_VALUES = {
    "social_only_cap": 0.39,
    "inference_only_cap": 0.49,
    "single_low_quality_source_cap": 0.39,
}

HOP_DECAY = {
    1: 1.00,
    2: 0.75,
    3: 0.55,
}

CONFIDENCE_BANDS = {
    "explicit": {
        "direct": (0.80, 0.95),
        "weak_mention": (0.45, 0.65),
    },
    "inferred": {
        "high": (0.65, 0.80),
        "medium": (0.45, 0.65),
        "stale_or_broad": (0.25, 0.45),
    },
    "market": {
        "strong": (0.70, 0.85),
        "moderate": (0.45, 0.65),
        "weak_or_noisy": (0.20, 0.40),
    },
    "social": {
        "corroborated": (0.35, 0.55),
        "uncorroborated": (0.20, 0.35),
    },
}

REACTION_SCORE_BY_STRENGTH = {
    "strong": 0.75,
    "moderate": 0.50,
    "weak": 0.25,
    "none": 0.00,
}
