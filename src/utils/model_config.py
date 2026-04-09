from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

_DEFAULT_CONFIG: dict[str, Any] = {
    'default_profile': 'economy',
    'profiles': {
        'economy': {
            'model': 'gpt-5.4-mini',
            'context_window': 400000,
            'max_output_tokens': 32000,
            'monthly_cost_estimate_usd': 0.31,
            'input_cost_per_1m_tokens': 0.25,
            'cached_input_cost_per_1m_tokens': 0.025,
            'output_cost_per_1m_tokens': 2.0,
        },
        'standard': {
            'model': 'gpt-5.4',
            'context_window': 400000,
            'max_output_tokens': 32000,
            'monthly_cost_estimate_usd': 3.0,
            'input_cost_per_1m_tokens': 1.25,
            'cached_input_cost_per_1m_tokens': 0.125,
            'output_cost_per_1m_tokens': 10.0,
        },
        'deep': {
            'model': 'o3-mini',
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
    context_window: int
    max_output_tokens: int
    monthly_cost_estimate_usd: float
    input_cost_per_1m_tokens: float
    cached_input_cost_per_1m_tokens: float
    output_cost_per_1m_tokens: float


def load_model_profile(path: str = 'config/models.yaml') -> ModelProfile:
    config = _load_model_config(path)
    profiles = config.get('profiles', {})
    default_profile_name = str(config.get('default_profile', 'economy'))
    requested_profile_name = os.getenv('OPENAI_MODEL_PROFILE', '').strip() or default_profile_name
    raw_profile = profiles.get(requested_profile_name) or profiles.get(default_profile_name) or next(iter(profiles.values()), {})

    profile = ModelProfile(
        name=requested_profile_name if requested_profile_name in profiles else default_profile_name,
        model=str(raw_profile.get('model', 'gpt-5.4-mini')),
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


def safe_input_token_budget(profile: ModelProfile) -> int:
    usable_window = int(profile.context_window * 0.8)
    return max(1024, usable_window - profile.max_output_tokens)


def _load_model_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return _DEFAULT_CONFIG
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(config_path.read_text(encoding='utf-8'))
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass
    return _DEFAULT_CONFIG
