"""Unit tests for src/collector/news_shadow_compare.py.

Shadow comparison is observation-only, so the surface area is narrow:
  * build_news_orchestrator registers SEC + IR providers
  * run_news_shadow_comparison logs a summary event, detail events for
    diffs, and never raises — even when the orchestrator blows up
  * IR tokens are sourced from WatchlistItem.ir_source_names and matched
    case-insensitively against NewsItem.source
"""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.collector.news_base import NewsResult
from src.collector.news_orchestrator import NewsCollectionReport
from src.collector.news_shadow_compare import (
    build_news_orchestrator,
    run_news_shadow_comparison,
)
from src.types import NewsItem, WatchlistItem


def _sec(title: str) -> NewsItem:
    return NewsItem(title=title, source="SEC EDGAR", link=f"https://sec/{title}")


def _ir(title: str, brand: str = "Apple Newsroom") -> NewsItem:
    return NewsItem(title=title, source=brand, link=f"https://ir/{title}")


def _unowned(title: str) -> NewsItem:
    # Source the orchestrator doesn't own (e.g., "fallback" placeholder,
    # Seeking Alpha, unrecognized blog). Must be excluded from the diff.
    return NewsItem(title=title, source="fallback", link=f"https://f/{title}")


def _wl_apple() -> WatchlistItem:
    return WatchlistItem(
        ticker="AAPL",
        name="Apple Inc.",
        cik="0000320193",
        ir_rss_feeds=["https://apple.com/newsroom/rss-feed.rss"],
        ir_source_names={"default": "Apple Newsroom"},
    )


class BuildNewsOrchestratorTests(unittest.TestCase):
    def test_registers_all_news_providers_in_trust_tier_order(self) -> None:
        orch = build_news_orchestrator()
        names = [p.name for p in orch.providers]
        # Highest trust first (SEC=4) → IR=2 → Google News=1 → DuckDuckGo=0.
        self.assertEqual(names, ["sec_edgar", "ir_rss", "google_news", "duckduckgo"])


class RunNewsShadowComparisonTests(unittest.TestCase):
    def _patched_collect(self, new_per_ticker: dict[str, list[NewsItem]]):
        """Patch NewsOrchestrator.collect_all to return the given map."""
        report = NewsCollectionReport()
        return patch(
            "src.collector.news_shadow_compare.NewsOrchestrator.collect_all",
            return_value=(new_per_ticker, report),
        )

    def test_summary_event_always_emitted(self) -> None:
        legacy = {"AAPL": [_sec("Apple 8-K")]}
        new = {"AAPL": [_sec("Apple 8-K")]}
        with patch(
            "src.collector.news_shadow_compare.record_pipeline_event"
        ) as logged, self._patched_collect(new):
            run_news_shadow_comparison([_wl_apple()], date(2026, 4, 15), legacy)

        events = [call.args[2] for call in logged.call_args_list]
        self.assertIn("news_shadow_comparison_summary", events)
        # No diffs, so only the summary event should fire.
        self.assertEqual(events, ["news_shadow_comparison_summary"])

    def test_missing_in_new_is_logged(self) -> None:
        # Legacy had the SEC filing, new orchestrator didn't return it.
        legacy = {"AAPL": [_sec("Apple 8-K"), _sec("Apple 10-Q")]}
        new = {"AAPL": [_sec("Apple 8-K")]}  # missing 10-Q
        with patch(
            "src.collector.news_shadow_compare.record_pipeline_event"
        ) as logged, self._patched_collect(new):
            run_news_shadow_comparison([_wl_apple()], date(2026, 4, 15), legacy)

        diff_events = [
            call.kwargs for call in logged.call_args_list
            if call.args[2] == "news_shadow_ticker_diff"
        ]
        self.assertEqual(len(diff_events), 1)
        self.assertEqual(diff_events[0]["direction"], "missing_in_new")
        self.assertEqual(diff_events[0]["count"], 1)
        self.assertIn("apple 10-q", diff_events[0]["sample_titles"])

    def test_extra_in_new_is_logged(self) -> None:
        legacy = {"AAPL": [_sec("Apple 8-K")]}
        new = {"AAPL": [_sec("Apple 8-K"), _sec("Apple 10-Q")]}  # extra
        with patch(
            "src.collector.news_shadow_compare.record_pipeline_event"
        ) as logged, self._patched_collect(new):
            run_news_shadow_comparison([_wl_apple()], date(2026, 4, 15), legacy)

        diff_events = [
            call.kwargs for call in logged.call_args_list
            if call.args[2] == "news_shadow_ticker_diff"
        ]
        self.assertEqual(len(diff_events), 1)
        self.assertEqual(diff_events[0]["direction"], "extra_in_new")
        self.assertIn("apple 10-q", diff_events[0]["sample_titles"])

    def test_third_party_sources_are_ignored(self) -> None:
        # Fallback/unrecognized-source items exist in legacy but must NOT
        # count as diffs — the NewsOrchestrator doesn't own those tokens.
        legacy = {
            "AAPL": [
                _sec("Apple 8-K"),
                _unowned("Apple fallback placeholder"),  # ignored
            ]
        }
        new = {"AAPL": [_sec("Apple 8-K")]}
        with patch(
            "src.collector.news_shadow_compare.record_pipeline_event"
        ) as logged, self._patched_collect(new):
            run_news_shadow_comparison([_wl_apple()], date(2026, 4, 15), legacy)

        events = [call.args[2] for call in logged.call_args_list]
        self.assertEqual(events.count("news_shadow_ticker_diff"), 0)

    def test_ir_brand_matching_is_case_insensitive(self) -> None:
        # Legacy tags the IR item with the brand (any casing), orchestrator
        # returns the same item — expected: no diff.
        legacy = {"AAPL": [_ir("Vision Pro launch", brand="Apple NEWSROOM")]}
        new = {"AAPL": [_ir("Vision Pro launch", brand="apple newsroom")]}
        with patch(
            "src.collector.news_shadow_compare.record_pipeline_event"
        ) as logged, self._patched_collect(new):
            run_news_shadow_comparison([_wl_apple()], date(2026, 4, 15), legacy)

        diff_events = [
            c for c in logged.call_args_list
            if c.args[2] == "news_shadow_ticker_diff"
        ]
        self.assertEqual(diff_events, [])

    def test_exception_in_orchestrator_is_caught(self) -> None:
        legacy = {"AAPL": [_sec("Apple 8-K")]}
        with patch(
            "src.collector.news_shadow_compare.record_pipeline_event"
        ) as logged, patch(
            "src.collector.news_shadow_compare.NewsOrchestrator.collect_all",
            side_effect=RuntimeError("kaboom"),
        ):
            # Must not raise — shadow is best-effort.
            run_news_shadow_comparison([_wl_apple()], date(2026, 4, 15), legacy)

        events = [call.args[2] for call in logged.call_args_list]
        self.assertIn("news_shadow_orchestrator_failed", events)

    def test_injected_orchestrator_is_used(self) -> None:
        # Allow tests / experiments to pass a pre-configured orchestrator.
        legacy = {"AAPL": []}
        from src.collector.news_orchestrator import NewsOrchestrator
        orch = NewsOrchestrator()  # empty — no providers registered

        with patch(
            "src.collector.news_shadow_compare.build_news_orchestrator"
        ) as builder, patch(
            "src.collector.news_shadow_compare.record_pipeline_event"
        ) as logged:
            run_news_shadow_comparison(
                [_wl_apple()], date(2026, 4, 15), legacy, orchestrator=orch
            )
            builder.assert_not_called()

        events = [call.args[2] for call in logged.call_args_list]
        self.assertIn("news_shadow_comparison_summary", events)


if __name__ == "__main__":
    unittest.main()
