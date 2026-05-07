import tempfile
import unittest
from pathlib import Path

from src.collector.search_evidence_config import SearchEvidenceConfig, load_search_evidence_config


class SearchEvidenceConfigTests(unittest.TestCase):
    def test_defaults_keep_search_evidence_cache_only(self) -> None:
        config = SearchEvidenceConfig()

        self.assertEqual(config.mode, "cache")
        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.max_search_tickers_per_run, 5)
        self.assertEqual(config.max_queries_per_ticker, 2)
        self.assertGreaterEqual(len(config.query_templates), 2)

    def test_load_search_evidence_config_reads_yaml_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "search_evidence.yaml"
            path.write_text(
                "\n".join(
                    [
                        "mode: openai",
                        "provider: openai",
                        "model_profile: standard",
                        "tool_type: web_search",
                        "max_search_tickers_per_run: 3",
                        "max_queries_per_ticker: 1",
                        "cache_ttl_hours: 12",
                        "requests_per_minute: 4",
                        "tokens_per_minute: 40000",
                        "rate_limit_timeout_seconds: 2",
                        "estimated_input_tokens_per_query: 700",
                        "estimated_output_tokens_per_query: 500",
                        "query_templates:",
                        "  - \"{ticker} latest earnings\"",
                        "  - \"{ticker} risk factors\"",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_search_evidence_config(str(path))

        self.assertEqual(config.mode, "openai")
        self.assertEqual(config.model_profile, "standard")
        self.assertEqual(config.max_search_tickers_per_run, 3)
        self.assertEqual(config.max_queries_per_ticker, 1)
        self.assertEqual(config.cache_ttl_hours, 12)
        self.assertEqual(config.requests_per_minute, 4)
        self.assertEqual(config.tokens_per_minute, 40000)
        self.assertEqual(config.rate_limit_timeout_seconds, 2.0)
        self.assertEqual(config.estimated_input_tokens_per_query, 700)
        self.assertEqual(config.estimated_output_tokens_per_query, 500)
        self.assertEqual(config.query_templates, ("{ticker} latest earnings", "{ticker} risk factors"))


if __name__ == "__main__":
    unittest.main()
