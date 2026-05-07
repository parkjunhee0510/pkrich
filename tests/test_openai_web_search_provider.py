import json
import unittest
from datetime import date

from src.collector.providers.search.openai_web_search import OpenAIWebSearchProvider


class _FakeResponse:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text


class _FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self.output_text)


class _FakeClient:
    def __init__(self, output_text: str) -> None:
        self.responses = _FakeResponses(output_text)


class OpenAIWebSearchProviderTests(unittest.TestCase):
    def test_search_calls_responses_api_and_normalizes_items(self) -> None:
        client = _FakeClient(
            json.dumps(
                {
                    "items": [
                        {
                            "title": "Coherent reports fiscal results",
                            "url": "https://investors.coherent.com/news/results",
                            "published_at": "2026-05-06",
                            "snippet": "AI datacenter demand supported revenue.",
                            "evidence_type": "earnings",
                            "relevance_score": 0.91,
                            "freshness_hours": 24,
                        }
                    ]
                }
            )
        )
        provider = OpenAIWebSearchProvider(
            model="gpt-5.4",
            tool_type="web_search",
            client=client,
        )

        items = provider.search(
            ticker="cohr",
            queries=["COHR latest earnings"],
            run_date=date(2026, 5, 7),
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].ticker, "COHR")
        self.assertEqual(items[0].query, "COHR latest earnings")
        self.assertEqual(items[0].title, "Coherent reports fiscal results")
        self.assertEqual(items[0].relevance_score, 0.91)
        self.assertEqual(items[0].freshness_hours, 24)

        call = client.responses.calls[0]
        self.assertEqual(call["model"], "gpt-5.4")
        self.assertEqual(call["tools"], [{"type": "web_search"}])
        self.assertIn("COHR latest earnings", call["input"])
        self.assertEqual(call["text"]["format"]["type"], "json_schema")

    def test_search_ignores_items_without_url(self) -> None:
        client = _FakeClient(
            json.dumps(
                {
                    "items": [
                        {
                            "title": "No source",
                            "url": "",
                            "published_at": "2026-05-06",
                            "snippet": "No source URL.",
                            "evidence_type": "news",
                            "relevance_score": 0.5,
                            "freshness_hours": 24,
                        }
                    ]
                }
            )
        )
        provider = OpenAIWebSearchProvider(model="gpt-5.4", client=client)

        items = provider.search(ticker="AAPL", queries=["AAPL latest"], run_date=date(2026, 5, 7))

        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
