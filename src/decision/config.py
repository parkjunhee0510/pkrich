from __future__ import annotations

from copy import deepcopy
from typing import Any

_FACTOR_ALIASES = {
    "catalyst": "catalyst_recency",
    "signal_record": "signal_track_record",
    "regime": "regime_adjustment",
    "earnings": "earnings_pattern",
}
_SUPPORTED_REGIMES = {"risk_on", "risk_off", "neutral"}
_DEFAULT_MULTIPLIER = 1.0
_MIN_MULTIPLIER = 0.1


def normalize_factor_name(name: str) -> str:
    return _FACTOR_ALIASES.get(name, name)


def normalize_decision_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(config)
    normalized["factors"] = _normalize_factor_section(normalized.get("factors", {}))
    normalized["regime_multipliers"] = _normalize_regime_multipliers(normalized.get("regime_multipliers", {}))
    return normalized


def multiplier_for(factor_name: str, regime_name: str, regime_multipliers: dict[str, dict[str, float]]) -> float:
    regime_key = regime_name if regime_name in _SUPPORTED_REGIMES else "neutral"
    value = regime_multipliers.get(regime_key, {}).get(factor_name, _DEFAULT_MULTIPLIER)
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid multiplier for {regime_key}.{factor_name}: {value}") from exc
    if numeric < 0:
        raise ValueError(f"Negative multiplier is not allowed for {regime_key}.{factor_name}")
    if numeric == 0:
        return _MIN_MULTIPLIER
    return max(_MIN_MULTIPLIER, numeric)


def _normalize_factor_section(factors: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for raw_name, bounds in factors.items():
        canonical = normalize_factor_name(str(raw_name))
        if canonical in normalized:
            raise ValueError(f"Duplicate factor config after alias normalization: {raw_name}")
        normalized[canonical] = bounds
    return normalized


def _normalize_regime_multipliers(regime_multipliers: dict[str, Any]) -> dict[str, dict[str, float]]:
    normalized: dict[str, dict[str, float]] = {regime: {} for regime in _SUPPORTED_REGIMES}
    for regime_name, multipliers in regime_multipliers.items():
        if regime_name not in _SUPPORTED_REGIMES:
            raise ValueError(f"Unsupported regime multiplier block: {regime_name}")
        if not isinstance(multipliers, dict):
            raise ValueError(f"Regime multiplier block must be an object: {regime_name}")
        for raw_factor_name, raw_value in multipliers.items():
            canonical = normalize_factor_name(str(raw_factor_name))
            if canonical in normalized[regime_name]:
                raise ValueError(f"Duplicate multiplier after alias normalization: {regime_name}.{raw_factor_name}")
            normalized[regime_name][canonical] = multiplier_for(canonical, regime_name, {regime_name: {canonical: raw_value}})
    return normalized
