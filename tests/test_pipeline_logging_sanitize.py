from __future__ import annotations

import unittest

from src.utils.pipeline_logging import _sanitize_fields


class SanitizeFieldsTests(unittest.TestCase):
    def test_strips_obvious_secrets(self) -> None:
        result = _sanitize_fields({
            'api_key': 'sk-xxx',
            'slack_webhook_url': 'https://hooks.slack.com/xxx',
            'auth_token': 'bearer xxx',
            'admin_password': 'nope',
            'some_secret': 'hidden',
            'safe': 1,
        })
        self.assertEqual(result, {'safe': 1})

    def test_preserves_token_telemetry_keys(self) -> None:
        """Regression: the substring filter for 'token' was stripping OpenAI
        usage fields (input_tokens, output_tokens, ...) because they contain
        the literal substring 'token'. That silently zeroed cost_log tokens
        and hid real LLM usage from operators.
        """
        result = _sanitize_fields({
            'input_tokens': 1000,
            'output_tokens': 500,
            'cached_input_tokens': 200,
            'total_tokens': 1500,
            'prompt_tokens': 800,
            'completion_tokens': 400,
            'max_output_tokens': 32000,
            'reasoning_tokens': 100,
        })
        self.assertEqual(result, {
            'input_tokens': 1000,
            'output_tokens': 500,
            'cached_input_tokens': 200,
            'total_tokens': 1500,
            'prompt_tokens': 800,
            'completion_tokens': 400,
            'max_output_tokens': 32000,
            'reasoning_tokens': 100,
        })

    def test_still_strips_token_credential_keys(self) -> None:
        result = _sanitize_fields({
            'auth_token': 'xxx',
            'access_token': 'xxx',
            'refresh_token': 'xxx',
            'api_token': 'xxx',
            'output_tokens': 500,  # telemetry, must survive
        })
        self.assertEqual(result, {'output_tokens': 500})


if __name__ == '__main__':
    unittest.main()
