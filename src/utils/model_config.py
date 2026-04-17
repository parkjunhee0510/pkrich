from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from src.utils.config import load_yaml_mapping

_DEFAULT_CONFIG: dict[str, Any] = {
    'default_profile': 'economy',
    'ensemble': {
        'enabled': True,
        'trigger_range': [25, 75],
        'second_model': 'deep',
        'second_prompt': 'research_v2',
        'third_model': 'standard',
        'third_prompt': 'research_v1',
        'max_daily_ensemble': 0,
    },
    'profiles': {
        'economy': {
            'model': 'gpt-5.4-mini',
            'prompt_version': 'research_v1',
            'context_window': 400000,
            'max_output_tokens': 32000,
            'monthly_cost_estimate_usd': 0.31,
            'input_cost_per_1m_tokens': 0.25,
            'cached_input_cost_per_1m_tokens': 0.025,
            'output_cost_per_1m_tokens': 2.0,
        },
        'standard': {
            'model': 'gpt-5.4',
            'prompt_version': 'research_v1',
            'context_window': 400000,
            'max_output_tokens': 32000,
            'monthly_cost_estimate_usd': 3.0,
            'input_cost_per_1m_tokens': 1.25,
            'cached_input_cost_per_1m_tokens': 0.125,
            'output_cost_per_1m_tokens': 10.0,
        },
        'deep': {
            'model': 'o3-mini',
            'prompt_version': 'research_v2',
            'context_window': 200000,
            'max_output_tokens': 100000,
            'monthly_cost_estimate_usd': 8.0,
            'input_cost_per_1m_tokens': 1.10,
            'cached_input_cost_per_1m_tokens': 0.55,
            'output_cost_per_1m_tokens': 4.40,
        },
    },
}


@dataclass(frozen=True)
class ModelProfile:
    name: str
    model: str
    prompt_version: str
    context_window: int
    max_output_tokens: int
    monthly_cost_estimate_usd: float
    input_cost_per_1m_tokens: float
    cached_input_cost_per_1m_tokens: float
    output_cost_per_1m_tokens: float


@dataclass(frozen=True)
class EnsembleConfig:
    enabled: bool
    trigger_range: tuple[int, int]
    second_model: str
    second_prompt: str
    third_model: str
    third_prompt: str
    max_daily_ensemble: int
    portfolio_priority: bool = False
    emit_routing_log: bool = True


def load_model_profile(path: str = 'config/models.yaml', *, profile_name: str | None = None) -> ModelProfile:
    config = _load_model_config(path)
    profiles = config.get('profiles', {})
    default_profile_name = str(config.get('default_profile', 'economy'))
    requested_profile_name = profile_name or os.getenv('OPENAI_MODEL_PROFILE', '').strip() or default_profile_name
    raw_profile = profiles.get(requested_profile_name) or profiles.get(default_profile_name) or next(iter(profiles.values()), {})

    profile = ModelProfile(
        name=requested_profile_name if requested_profile_name in profiles else default_profile_name,
        model=str(raw_profile.get('model', 'gpt-5.4-mini')),
        prompt_version=str(raw_profile.get('prompt_version', 'research_v1')),
        context_window=int(raw_profile.get('context_window', 400000)),
        max_output_tokens=int(raw_profile.get('max_output_tokens', 32000)),
        monthly_cost_estimate_usd=float(raw_profile.get('monthly_cost_estimate_usd', 0.0)),
        input_cost_per_1m_tokens=float(raw_profile.get('input_cost_per_1m_tokens', 0.0)),
        cached_input_cost_per_1m_tokens=float(raw_profile.get('cached_input_cost_per_1m_tokens', 0.0)),
        output_cost_per_1m_tokens=float(raw_profile.get('output_cost_per_1m_tokens', 0.0)),
    )

    manual_model = os.getenv('OPENAI_MODEL', '').strip()
    if manual_model:
        profile = replace(profile, model=manual_model)
    return profile


def build_model_profile(model: str, *, name: str = 'custom') -> ModelProfile:
    base = load_model_profile()
    return replace(base, name=name, model=model)


def load_ensemble_config(path: str = 'config/models.yaml') -> EnsembleConfig:
    config = _load_model_config(path)
    ensemble = config.get('ensemble', {}) or {}
    profiles = config.get('profiles', {}) or {}
    raw_range = ensemble.get('trigger_range', [25, 75])
    if not isinstance(raw_range, (list, tuple)) or len(raw_range) != 2:
        raise ValueError('ensemble.trigger_range must be a two-item list')
    try:
        low = int(raw_range[0])
        high = int(raw_range[1])
    except (TypeError, ValueError) as exc:
        raise ValueError('ensemble.trigger_range must contain integers') from exc
    if low < 0 or high > 100 or low > high:
        raise ValueError('ensemble.trigger_range must satisfy 0 <= low <= high <= 100')

    second_model = str(ensemble.get('second_model', 'deep')).strip() or 'deep'
    if second_model not in profiles:
        raise ValueError(f'ensemble.second_model must reference a configured profile: {second_model}')

    second_prompt = str(
        ensemble.get('second_prompt', profiles.get(second_model, {}).get('prompt_version', 'research_v2'))
    ).strip() or str(profiles.get(second_model, {}).get('prompt_version', 'research_v2'))
    third_model = str(ensemble.get('third_model', 'standard')).strip() or 'standard'
    if third_model not in profiles:
        raise ValueError(f'ensemble.third_model must reference a configured profile: {third_model}')
    third_prompt = str(
        ensemble.get('third_prompt', profiles.get(third_model, {}).get('prompt_version', 'research_v1'))
    ).strip() or str(profiles.get(third_model, {}).get('prompt_version', 'research_v1'))
    max_daily_ensemble = int(ensemble.get('max_daily_ensemble', 5))
    if max_daily_ensemble < 0:
        raise ValueError('ensemble.max_daily_ensemble must be >= 0')

    return EnsembleConfig(
        enabled=bool(ensemble.get('enabled', True)),
        trigger_range=(low, high),
        second_model=second_model,
        second_prompt=second_prompt,
        third_model=third_model,
        third_prompt=third_prompt,
        max_daily_ensemble=max_daily_ensemble,
        portfolio_priority=bool(ensemble.get('portfolio_priority', False)),
        emit_routing_log=bool(ensemble.get('emit_routing_log', True)),
    )


def safe_input_token_budget(profile: ModelProfile) -> int:
    usable_window = int(profile.context_window * 0.8)
    return max(1024, usable_window - profile.max_output_tokens)


def _load_model_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return _DEFAULT_CONFIG
    loaded = load_yaml_mapping(path, optional=True)
    return loaded if loaded else _DEFAULT_CONFIG
