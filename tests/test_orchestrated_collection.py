"""Unit tests for src/collector/orchestrated_collection.py.

This module is the seam between pipeline.py and the plugin architecture.
The tests here verify three contracts:

  1. `build_full_orchestrator` wires all data providers in priority order
     and forwards benchmark_change_30d to YFinance so RS-vs-SPY works.
  2. `collect_market_data_via_orchestrator` returns only the legacy
     dict[ticker, CollectedTickerData] shape, unwrapping the tuple, and
     logs the diagnostic report via record_pipeline_event.
  3. `collect_news_via_orchestrator` defaults to build_news_orchestrator
     when no orchestrator is injected, returns only the per-ticker dict,
     and logs the NewsCollectionReport summary.

All orchestrator/provider instances are either constructed directly
(for metadata assertions) or replaced via `patch` so no network I/O
occurs.
"""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from src.collector.news_orchestrator import NewsCollectionReport
from src.collector.orchestrated_collection import (
    build_full_orchestrator,
    collect_market_data_via_orchestrator,
    collect_news_via_orchestrator,
)
from src.collector.orchestrator import OrchestrationReport
from src.types import CollectedTickerData, WatchlistItem


def _wl(ticker: str = "AAPL") -> WatchlistItem:
    return WatchlistItem(ticker=ticker, name=f"{ticker} Inc.")


def _ctd(ticker: str = "AAPL") -> CollectedTickerData:
    return CollectedTickerData(
        ticker=ticker,
        name=f"{ticker} Inc.",
        sector="Technology",
        price=100.0,
        change_percent=1.0,
        currency="USD",
        market_cap="N/A",
        pe_ratio="N/A",
        summary_note="",
    )


class BuildFullOrchestratorTests(unittest.TestCase):
    def test_registers_eight_providers(self) -> None:
        orch = build_full_orchestrator()
        names = {p.name for p in orch._registry.all()}
        self.assertEqual(
            names,
            {
                "yfinance",
                "sector_etf",
                "fmp",
                "finnhub",
                "polygon",
                "toss_invest",
                "alpha_vantage",
                "stooq",
            },
        )

    def test_forwards_benchmark_change_to_yfinance(self) -> None:
        orch = build_full_orchestrator(benchmark_change_30d=4.2)
        yf = next(p for p in orch._registry.all() if p.name == "yfinance")
        # YFinanceProvider stores the benchmark on construction; the exact
        # attribute name is an implementation detail but the value must
        # flow through.
        found = any(
            getattr(yf, attr, None) == 4.2
            for attr in dir(yf)
            if not attr.startswith("_")
        ) or getattr(yf, "_benchmark_change_30d", None) == 4.2
        self.assertTrue(found, "benchmark_change_30d was not forwarded to YFinanceProvider")

    def test_benchmark_defaults_to_none(self) -> None:
        # Must not raise when benchmark is omitted (default path).
        orch = build_full_orchestrator()
        self.assertIsNotNone(orch)


class CollectMarketDataViaOrchestratorTests(unittest.TestCase):
    def test_returns_only_collected_dict_not_tuple(self) -> None:
        fake_collected = {"AAPL": _ctd("AAPL")}
        fake_report = OrchestrationReport(
            results_by_ticker={"AAPL": []},
            total_duration_ms=123,
        )
        with patch(
            "src.collector.orchestrated_collection.build_full_orchestrator"
        ) as builder, patch(
            "src.collector.orchestrated_collection.record_pipeline_event"
        ):
            orch_mock = MagicMock()
            orch_mock.collect_all.return_value = (fake_collected, fake_report)
            builder.return_value = orch_mock

            result = collect_market_data_via_orchestrator([_wl()], date(2026, 4, 15))

        self.assertIsInstance(result, dict)
        self.assertIn("AAPL", result)
        self.assertIs(result, fake_collected)

    def test_logs_pipeline_event_with_report_fields(self) -> None:
        fake_collected: dict[str, CollectedTickerData] = {}
        fake_report = OrchestrationReport(
            results_by_ticker={}, total_duration_ms=987,
        )
        with patch(
            "src.collector.orchestrated_collection.build_full_orchestrator"
        ) as builder, patch(
            "src.collector.orchestrated_collection.record_pipeline_event"
        ) as logged:
            orch_mock = MagicMock()
            orch_mock.collect_all.return_value = (fake_collected, fake_report)
            builder.return_value = orch_mock

            collect_market_data_via_orchestrator(
                [_wl("AAPL"), _wl("MSFT")], date(2026, 4, 15)
            )

        self.assertTrue(logged.called)
        # Find the orchestrator_primary_completed event.
        calls = [c for c in logged.call_args_list if c.args[2] == "orchestrator_primary_completed"]
        self.assertEqual(len(calls), 1)
        kwargs = calls[0].kwargs
        self.assertEqual(kwargs["tickers_total"], 2)
        self.assertEqual(kwargs["duration_ms"], 987)
        # failure_count is 0 because results_by_ticker is empty.
        self.assertEqual(kwargs["failures"], 0)

    def test_forwards_benchmark_change_to_builder(self) -> None:
        with patch(
            "src.collector.orchestrated_collection.build_full_orchestrator"
        ) as builder, patch(
            "src.collector.orchestrated_collection.record_pipeline_event"
        ):
            orch_mock = MagicMock()
            orch_mock.collect_all.return_value = ({}, OrchestrationReport())
            builder.return_value = orch_mock

            collect_market_data_via_orchestrator(
                [_wl()], date(2026, 4, 15), benchmark_change_30d=2.5
            )

        # Phase 1-1: builder now receives max_workers alongside the benchmark.
        builder.assert_called_once()
        call_kwargs = builder.call_args.kwargs
        self.assertEqual(call_kwargs["benchmark_change_30d"], 2.5)
        # Default resolves to _DEFAULT_MAX_WORKERS when env var is unset and
        # no override supplied. We assert >=1 rather than the exact default
        # so the test survives env-var customization on the developer's box.
        self.assertGreaterEqual(call_kwargs["max_workers"], 1)

    def test_forwards_max_workers_override_to_builder(self) -> None:
        with patch(
            "src.collector.orchestrated_collection.build_full_orchestrator"
        ) as builder, patch(
            "src.collector.orchestrated_collection.record_pipeline_event"
        ):
            orch_mock = MagicMock()
            orch_mock.collect_all.return_value = ({}, OrchestrationReport())
            builder.return_value = orch_mock

            collect_market_data_via_orchestrator(
                [_wl()], date(2026, 4, 15), max_workers=7
            )

        builder.assert_called_once()
        self.assertEqual(builder.call_args.kwargs["max_workers"], 7)


class CollectNewsViaOrchestratorTests(unittest.TestCase):
    def test_uses_injected_orchestrator_when_provided(self) -> None:
        injected = MagicMock()
        injected.collect_all.return_value = (
            {"AAPL": []},
            NewsCollectionReport(),
        )
        with patch(
            "src.collector.orchestrated_collection.build_news_orchestrator"
        ) as builder, patch(
            "src.collector.orchestrated_collection.record_pipeline_event"
        ):
            result = collect_news_via_orchestrator(
                [_wl()], date(2026, 4, 15), orchestrator=injected
            )

        builder.assert_not_called()
        injected.collect_all.assert_called_once()
        self.assertEqual(result, {"AAPL": []})

    def test_builds_default_orchestrator_when_none_injected(self) -> None:
        with patch(
            "src.collector.orchestrated_collection.build_news_orchestrator"
        ) as builder, patch(
            "src.collector.orchestrated_collection.record_pipeline_event"
        ):
            built = MagicMock()
            built.collect_all.return_value = ({}, NewsCollectionReport())
            builder.return_value = built

            collect_news_via_orchestrator([_wl()], date(2026, 4, 15))

        builder.assert_called_once_with()
        built.collect_all.assert_called_once()

    def test_logs_summary_event(self) -> None:
        injected = MagicMock()
        report = NewsCollectionReport(
            per_ticker_counts={"AAPL": 3, "MSFT": 1},
            per_provider_counts={"sec_edgar": 2, "ir_rss": 2},
            provider_failures=[("ir_rss", "AAPL", "feed unavailable")],
        )
        injected.collect_all.return_value = ({"AAPL": [], "MSFT": []}, report)

        with patch(
            "src.collector.orchestrated_collection.record_pipeline_event"
        ) as logged:
            collect_news_via_orchestrator(
                [_wl("AAPL"), _wl("MSFT")],
                date(2026, 4, 15),
                orchestrator=injected,
            )

        events = [c for c in logged.call_args_list if c.args[2] == "news_orchestrator_primary_completed"]
        self.assertEqual(len(events), 1)
        kwargs = events[0].kwargs
        self.assertEqual(kwargs["tickers_total"], 2)
        self.assertEqual(kwargs["total_items"], 4)
        self.assertEqual(kwargs["provider_failures"], 1)
        self.assertEqual(kwargs["per_provider_counts"], {"sec_edgar": 2, "ir_rss": 2})

    def test_returns_only_per_ticker_dict_not_tuple(self) -> None:
        injected = MagicMock()
        injected.collect_all.return_value = (
            {"AAPL": []},
            NewsCollectionReport(),
        )
        with patch(
            "src.collector.orchestrated_collection.record_pipeline_event"
        ):
            result = collect_news_via_orchestrator(
                [_wl()], date(2026, 4, 15), orchestrator=injected
            )

        self.assertIsInstance(result, dict)
        self.assertNotIsInstance(result, tuple)


if __name__ == "__main__":
    unittest.main()
