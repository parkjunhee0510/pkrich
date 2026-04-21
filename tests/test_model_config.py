from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.utils.cost_tracker import calculate_response_cost
from src.utils.model_config import (
    load_ensemble_config,
    load_model_profile,
    resolve_module_model_profile,
    safe_input_token_budget,
)


class ModelConfigTests(unittest.TestCase):
    def test_default_profile_includes_prompt_version(self) -> None:
        profile = load_model_profile()
        self.assertTrue(profile.prompt_version)

    def test_load_model_profile_prefers_profile_then_model_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / 'models.yaml'
            config_path.write_text(
                '\n'.join(
                    [
                        'default_profile: economy',
                        'profiles:',
                        '  economy:',
                        '    model: gpt-5.4-mini',
                        '    prompt_version: research_v1',
                        '    context_window: 400000',
                        '    max_output_tokens: 32000',
                        '    monthly_cost_estimate_usd: 0.31',
                        '    input_cost_per_1m_tokens: 0.25',
                        '    cached_input_cost_per_1m_tokens: 0.025',
                        '    output_cost_per_1m_tokens: 2.0',
                        '  standard:',
                        '    model: gpt-5.4',
                        '    prompt_version: research_v2',
                        '    context_window: 300000',
                        '    max_output_tokens: 16000',
                        '    monthly_cost_estimate_usd: 3.0',
                        '    input_cost_per_1m_tokens: 1.25',
                        '    cached_input_cost_per_1m_tokens: 0.125',
                        '    output_cost_per_1m_tokens: 10.0',
                    ]
                ),
                encoding='utf-8',
            )

            with patch.dict(os.environ, {'OPENAI_MODEL_PROFILE': 'standard', 'OPENAI_MODEL': 'custom-model'}, clear=False):
                profile = load_model_profile(str(config_path))

        self.assertEqual(profile.name, 'standard')
        self.assertEqual(profile.model, 'custom-model')
        self.assertEqual(profile.prompt_version, 'research_v2')
        self.assertEqual(profile.context_window, 300000)
        self.assertEqual(safe_input_token_budget(profile), int(300000 * 0.8) - 16000)

    def test_calculate_response_cost_uses_usage_and_cached_tokens(self) -> None:
        response = SimpleNamespace(
            usage=SimpleNamespace(
                input_tokens=1200,
                output_tokens=300,
                total_tokens=1500,
                input_tokens_details=SimpleNamespace(cached_tokens=200),
            )
        )
        profile = load_model_profile()

        cost = calculate_response_cost(response, profile)

        self.assertEqual(cost.input_tokens, 1200)
        self.assertEqual(cost.output_tokens, 300)
        self.assertEqual(cost.cached_input_tokens, 200)
        self.assertGreater(cost.estimated_cost_usd, 0.0)

    def test_resolve_module_model_profile_uses_override_profile_but_keeps_prompt_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / 'models.yaml'
            config_path.write_text(
                '\n'.join(
                    [
                        'default_profile: economy',
                        'module_profile_overrides:',
                        '  signal_takeaway_module: standard',
                        'profiles:',
                        '  economy:',
                        '    model: gpt-5.4-mini',
                        '    prompt_version: research_v2',
                        '    context_window: 400000',
                        '    max_output_tokens: 32000',
                        '    monthly_cost_estimate_usd: 0.31',
                        '    input_cost_per_1m_tokens: 0.25',
                        '    cached_input_cost_per_1m_tokens: 0.025',
                        '    output_cost_per_1m_tokens: 2.0',
                        '  standard:',
                        '    model: gpt-5.4',
                        '    prompt_version: research_v1',
                        '    context_window: 400000',
                        '    max_output_tokens: 32000',
                        '    monthly_cost_estimate_usd: 3.0',
                        '    input_cost_per_1m_tokens: 1.25',
                        '    cached_input_cost_per_1m_tokens: 0.125',
                        '    output_cost_per_1m_tokens: 10.0',
                    ]
                ),
                encoding='utf-8',
            )

            base_profile = load_model_profile(str(config_path), profile_name='economy')
            resolved = resolve_module_model_profile(base_profile, 'signal_takeaway_module', str(config_path))

        self.assertEqual(resolved.model, 'gpt-5.4')
        self.assertEqual(resolved.name, 'standard')
        self.assertEqual(resolved.prompt_version, 'research_v2')

    def test_load_ensemble_config_reads_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / 'models.yaml'
            config_path.write_text(
                '\n'.join(
                    [
                        'default_profile: economy',
                        'ensemble:',
                        '  enabled: true',
                        '  trigger_range: [25, 75]',
                        '  second_model: deep',
                        '  second_prompt: research_v2',
                        '  max_daily_ensemble: 3',
                        'profiles:',
                        '  economy:',
                        '    model: gpt-5.4-mini',
                        '    prompt_version: research_v1',
                        '    context_window: 400000',
                        '    max_output_tokens: 32000',
                        '    monthly_cost_estimate_usd: 0.31',
                        '    input_cost_per_1m_tokens: 0.25',
                        '    cached_input_cost_per_1m_tokens: 0.025',
                        '    output_cost_per_1m_tokens: 2.0',
                        '  deep:',
                        '    model: o3-mini',
                        '    prompt_version: research_v2',
                        '    context_window: 200000',
                        '    max_output_tokens: 100000',
                        '    monthly_cost_estimate_usd: 8.0',
                        '    input_cost_per_1m_tokens: 1.10',
                        '    cached_input_cost_per_1m_tokens: 0.55',
                        '    output_cost_per_1m_tokens: 4.40',
                    ]
                ),
                encoding='utf-8',
            )

            ensemble = load_ensemble_config(str(config_path))

        self.assertTrue(ensemble.enabled)
        self.assertEqual(ensemble.trigger_range, (25, 75))
        self.assertEqual(ensemble.second_model, 'deep')
        self.assertEqual(ensemble.second_prompt, 'research_v2')
        self.assertEqual(ensemble.max_daily_ensemble, 3)

    def test_load_ensemble_config_rejects_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / 'models.yaml'
            config_path.write_text(
                '\n'.join(
                    [
                        'default_profile: economy',
                        'ensemble:',
                        '  enabled: true',
                        '  trigger_range: [90, 20]',
                        '  second_model: missing',
                        '  second_prompt: research_v2',
                        '  max_daily_ensemble: 3',
                        'profiles:',
                        '  economy:',
                        '    model: gpt-5.4-mini',
                        '    prompt_version: research_v1',
                        '    context_window: 400000',
                        '    max_output_tokens: 32000',
                        '    monthly_cost_estimate_usd: 0.31',
                        '    input_cost_per_1m_tokens: 0.25',
                        '    cached_input_cost_per_1m_tokens: 0.025',
                        '    output_cost_per_1m_tokens: 2.0',
                    ]
                ),
                encoding='utf-8',
            )

            with self.assertRaises(ValueError):
                load_ensemble_config(str(config_path))


if __name__ == '__main__':
    unittest.main()
