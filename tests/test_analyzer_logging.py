from __future__ import annotations

import json
import unittest

from src.analyzer.research_note import _build_log_message


class AnalyzerLoggingTests(unittest.TestCase):
    def test_build_log_message_returns_structured_json(self) -> None:
        message = _build_log_message(
            "openai_response_validation_failed",
            model="gpt-4o-mini",
            ticker_count=3,
            error_type="ValueError",
        )

        payload = json.loads(message)

        self.assertEqual(payload["event"], "openai_response_validation_failed")
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertEqual(payload["ticker_count"], 3)
        self.assertEqual(payload["error_type"], "ValueError")


if __name__ == "__main__":
    unittest.main()
