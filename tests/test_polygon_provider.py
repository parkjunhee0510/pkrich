"""Unit tests for src/collector/providers/polygon_provider.py."""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.collector.base import CollectionContext
from src.collector.providers.polygon_provider import PolygonProvider
from src.types import WatchlistItem


def _ctx(ticker: str = "AAPL", cache_store: dict[tuple[str, str], object] | None = None) -> CollectionContext:
    cache_store = cache_store or {}

    def cache_get(provider: str, key: str):
        value = cache_store.get((provider, key))
        if value is None:
            return None

        class Entry:
            def __init__(self, payload: object) -> None:
                self.payload = payload

        return Entry(value)

    def cache_set(provider: str, key: str, payload: object, ttl_hours: float) -> None:  # noqa: ARG001
        cache_store[(provider, key)] = payload

    return CollectionContext(
        watchlist_item=WatchlistItem(ticker=ticker, name=f"{ticker} Inc.", sector="Tech"),
        run_date=date(2026, 4, 15),
        extra={"cache_get": cache_get, "cache_set": cache_set},
    )


class PolygonProviderMetadataTests(unittest.TestCase):
    def test_metadata(self) -> None:
        p = PolygonProvider()
        self.assertEqual(p.name, "polygon")
        self.assertEqual(p.priority, 2)
        self.assertEqual(p.provides, {"options_flow", "options_summary"})

    def test_is_available_delegates_to_module(self) -> None:
        p = PolygonProvider()
        with patch("src.collector.providers.polygon_provider.polygon_module.is_polygon_ready", return_value=True):
            self.assertTrue(p.is_available())
        with patch("src.collector.providers.polygon_provider.polygon_module.is_polygon_ready", return_value=False):
            self.assertFalse(p.is_available())
        with patch("src.collector.providers.polygon_provider.polygon_module.is_polygon_ready", side_effect=RuntimeError):
            self.assertFalse(p.is_available())


class PolygonProviderCollectTests(unittest.TestCase):
    def test_collect_returns_success_with_enriched_flow_and_summary(self) -> None:
        raw_snapshot = {"results": [{"dummy": True}]}
        base_flow = {
            "put_call_volume_ratio": "0.72",
            "flow_sentiment": "bullish",
            "max_pain": "$250 (+1.2% vs spot)",
            "implied_move": "?3.4% ($8.43) over 30d",
            "gex_regime": "positive $412M",
            "avg_iv": "28.5%",
        }
        metrics = {
            "total_call_oi": 1000.0,
            "total_put_oi": 700.0,
            "total_call_volume": 500.0,
            "total_put_volume": 360.0,
            "put_call_volume_ratio": "0.72",
            "put_call_oi_ratio": "0.70",
            "unusual_contracts": [
                {
                    "side": "CALL",
                    "strike": "270",
                    "volume": 8200,
                    "oi": 18000,
                    "vol_oi_ratio": 0.4555,
                    "premium_usd": 90000.0,
                    "expiry": "2026-05-15",
                }
            ],
        }
        cache_store = {
            ("polygon", "AAPL:options_snapshot:2026-04-14"): {
                "total_call_oi": 800.0,
                "total_put_oi": 600.0,
                "put_call_volume_ratio": "0.95",
            },
            ("polygon", "AAPL:options_snapshot:2026-04-13"): {
                "put_call_volume_ratio": "1.10",
            },
        }
        p = PolygonProvider()
        with patch("src.collector.providers.polygon_provider.polygon_module.fetch_options_snapshot", return_value=raw_snapshot), \
             patch("src.collector.providers.polygon_provider.polygon_module.build_options_flow_from_snapshot", return_value=base_flow), \
             patch("src.collector.providers.polygon_provider.polygon_module.extract_snapshot_metrics", return_value=metrics):
            result = p.collect("AAPL", _ctx(cache_store=cache_store))

        self.assertTrue(result.ok)
        fields = result.data.fields
        self.assertIn("options_flow", fields)
        self.assertIn("options_summary", fields)
        self.assertEqual(fields["options_flow"]["put_oi_change_pct"], "+16.7%")
        self.assertEqual(fields["options_flow"]["call_oi_change_pct"], "+25.0%")
        self.assertEqual(fields["options_flow"]["options_tone"], "bullish")
        self.assertEqual(fields["options_flow"]["unusual_activity_flag"], "true")
        self.assertIn("CALL $270", fields["options_flow"]["unusual_activity"])
        self.assertEqual(fields["options_summary"]["tone"], "bullish")
        self.assertIn("46%", fields["options_summary"]["unusual_activity"])
        self.assertIn("+25.0%", fields["options_summary"]["oi_change"])
        self.assertIn("+16.7%", fields["options_summary"]["oi_change"])
        self.assertIn(("polygon", "AAPL:options_snapshot:2026-04-15"), cache_store)

    def test_collect_gracefully_handles_missing_previous_snapshot(self) -> None:
        raw_snapshot = {"results": [{"dummy": True}]}
        base_flow = {"put_call_volume_ratio": "1.05"}
        metrics = {
            "total_call_oi": 1000.0,
            "total_put_oi": 1000.0,
            "put_call_volume_ratio": "1.05",
            "put_call_oi_ratio": "1.00",
            "unusual_contracts": [],
        }
        p = PolygonProvider()
        with patch("src.collector.providers.polygon_provider.polygon_module.fetch_options_snapshot", return_value=raw_snapshot), \
             patch("src.collector.providers.polygon_provider.polygon_module.build_options_flow_from_snapshot", return_value=base_flow), \
             patch("src.collector.providers.polygon_provider.polygon_module.extract_snapshot_metrics", return_value=metrics):
            result = p.collect("AAPL", _ctx(cache_store={}))

        self.assertTrue(result.ok)
        self.assertEqual(result.data.fields["options_flow"]["put_oi_change_pct"], "N/A")
        self.assertEqual(result.data.fields["options_summary"]["oi_change"], "N/A")
        self.assertEqual(result.data.fields["options_summary"]["tone"], "neutral")

    def test_collect_returns_failure_when_empty(self) -> None:
        p = PolygonProvider()
        with patch("src.collector.providers.polygon_provider.polygon_module.fetch_options_snapshot", return_value={}):
            result = p.collect("XYZ", _ctx("XYZ"))
        self.assertEqual(result.status, "failure")
        self.assertEqual(result.reason, "no_options_data")

    def test_collect_never_raises_on_exception(self) -> None:
        p = PolygonProvider()
        with patch("src.collector.providers.polygon_provider.polygon_module.fetch_options_snapshot", side_effect=RuntimeError("429 rate limited")):
            result = p.collect("AAPL", _ctx())
        self.assertEqual(result.status, "failure")
        self.assertIn("429", result.reason)


if __name__ == "__main__":
    unittest.main()
