import os
import tempfile
import unittest
from unittest.mock import patch

from src.collector.policy_events import (
    extract_events,
    filter_events,
    hash_event_id,
    load_cache,
    save_cache,
    prune_cache,
)


def _raw(**over):
    base = {
        "headline": "h",
        "summary": "s",
        "raw_excerpt": "r",
        "source_url": "https://ustr.gov/x",
        "published_at": "2026-04-27T01:00:00Z",
        "category": "tariff",
        "confidence": 0.6,
    }
    base.update(over)
    return base


class TestFilters(unittest.TestCase):
    def test_drops_event_without_source_url(self):
        out = filter_events(
            [_raw(source_url="")], today="2026-04-27",
            trusted=[], penalized=[], trust_bonus=0.2, penalty=0.3,
        )
        self.assertEqual(out, [])

    def test_drops_event_older_than_24h(self):
        out = filter_events(
            [_raw(published_at="2026-04-24T00:00:00Z")],
            today="2026-04-27", trusted=[], penalized=[],
            trust_bonus=0.2, penalty=0.3,
        )
        self.assertEqual(out, [])

    def test_drops_event_with_unparseable_published_at(self):
        out = filter_events(
            [_raw(published_at="not-an-iso")],
            today="2026-04-27", trusted=[], penalized=[],
            trust_bonus=0.2, penalty=0.3,
        )
        self.assertEqual(out, [])

    def test_trusted_domain_boosts_confidence(self):
        out = filter_events(
            [_raw(source_url="https://whitehouse.gov/x", confidence=0.5)],
            today="2026-04-27",
            trusted=["whitehouse.gov"], penalized=[],
            trust_bonus=0.2, penalty=0.3,
        )
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].confidence, 0.7, places=2)

    def test_penalized_domain_drops_confidence(self):
        out = filter_events(
            [_raw(source_url="https://reddit.com/x", confidence=0.6)],
            today="2026-04-27",
            trusted=[], penalized=["reddit.com"],
            trust_bonus=0.2, penalty=0.3,
        )
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].confidence, 0.3, places=2)

    def test_unknown_category_falls_back_to_other(self):
        out = filter_events(
            [_raw(category="zomg_unknown")],
            today="2026-04-27", trusted=[], penalized=[],
            trust_bonus=0.2, penalty=0.3,
        )
        self.assertEqual(out[0].category, "other")

    def test_dedupes_by_id(self):
        a = _raw()
        b = _raw()
        out = filter_events([a, b], today="2026-04-27",
                            trusted=[], penalized=[],
                            trust_bonus=0.2, penalty=0.3)
        self.assertEqual(len(out), 1)


class TestHashAndCache(unittest.TestCase):
    def test_hash_is_stable_and_short(self):
        a = hash_event_id("h", "https://x", "2026-04-27T00:00:00Z")
        b = hash_event_id("h", "https://x", "2026-04-27T00:00:00Z")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 12)

    def test_round_trip_cache(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "cache.json")
            save_cache(p, {"abc": "2026-04-27"})
            self.assertEqual(load_cache(p), {"abc": "2026-04-27"})

    def test_load_missing_cache_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "missing.json")
            self.assertEqual(load_cache(p), {})

    def test_prune_cache_drops_old_entries(self):
        cache = {
            "fresh": "2026-04-25",
            "old":   "2026-04-15",
        }
        pruned = prune_cache(cache, today="2026-04-27", days=7)
        self.assertIn("fresh", pruned)
        self.assertNotIn("old", pruned)


class TestExtract(unittest.TestCase):
    @patch("src.collector.policy_events._openai_web_search")
    def test_extract_calls_openai_and_filters(self, mock_search):
        mock_search.return_value = [_raw(source_url="https://ustr.gov/x")]
        with tempfile.TemporaryDirectory() as d:
            cache_path = os.path.join(d, "cache.json")
            events = extract_events(
                today="2026-04-27", model_profile="deep",
                sources_config={
                    "trusted_domains": ["ustr.gov"],
                    "penalized_domains": [],
                    "trust_bonus": 0.2, "penalty": 0.3,
                },
                cache_path=cache_path,
            )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source_domain, "ustr.gov")

    @patch("src.collector.policy_events._openai_web_search")
    def test_extract_writes_cache(self, mock_search):
        mock_search.return_value = [_raw()]
        with tempfile.TemporaryDirectory() as d:
            cache_path = os.path.join(d, "cache.json")
            extract_events(
                today="2026-04-27", model_profile="deep",
                sources_config={"trusted_domains": [], "penalized_domains": [],
                                "trust_bonus": 0.2, "penalty": 0.3},
                cache_path=cache_path,
            )
            cache = load_cache(cache_path)
        self.assertEqual(len(cache), 1)


if __name__ == "__main__":
    unittest.main()
