from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.utils.cost_tracker import calculate_response_cost
from src.utils.model_config import load_model_profile, safe_input_token_budget


class ModelConfigTests(unittest.TestCase):
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
                        '    context_window: 400000',
                        '    max_output_tokens: 32000',
                        '    monthly_cost_estimate_usd: 0.31',
                        '    input_cost_per_1m_tokens: 0.25',
                        '    cached_input_cost_per_1m_tokens: 0.025',
                        '    output_cost_per_1m_tokens: 2.0',
                        '  standard:',
                        '    model: gpt-5.4',
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


if __name__ == '__main__':
    unittest.main()
