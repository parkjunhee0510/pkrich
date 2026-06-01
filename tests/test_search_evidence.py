import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.collector.search_evidence_config import SearchEvidenceConfig
from src.collector.search_evidence import (
    SearchEvidenceItem,
    build_search_evidence_payload,
    collect_search_evidence,
    query_hash,
)
from src.collector.search_evidence_priority import REASON_HIGH_VOLATILITY
from src.utils.budget_guard import BudgetGuardConfig


class _FakeSearchProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def search(self, *, ticker: str, queries: list[str], run_date: date) -> list[SearchEvidenceItem]:
        self.calls.append((ticker, queries))
        return [
            SearchEvidenceItem(
                ticker=ticker,
                query=queries[0],
                title=f"{ticker} evidence",
                url=f"https://example.com/{ticker.lower()}",
                published_at=run_date.isoformat(),
                snippet="Recent evidence.",
                evidence_type="news",
                relevance_score=0.8,
                freshness_hours=12,
            )
        ]


class _FailingSearchProvider:
    def search(self, *, ticker: str, queries: list[str], run_date: date) -> list[SearchEvidenceItem]:
        raise RuntimeError(f"{ticker} provider failed")


class SearchEvidenceTests(unittest.TestCase):
    def test_item_to_dict_normalizes_ticker_domain_and_query_hash(self) -> None:
        item = SearchEvidenceItem(
            ticker="cohr",
            query="COHR latest earnings",
            title="Coherent results",
            url="https://investors.coherent.com/news/results",
            published_at="2026-05-04",
            snippet="Revenue improved.",
            evidence_type="earnings",
            relevance_score=0.88,
            freshness_hours=72,
        )

        payload = item.to_dict()

        self.assertEqual(payload["ticker"], "COHR")
        self.assertEqual(payload["source_domain"], "investors.coherent.com")
        self.assertEqual(payload["query_hash"], query_hash("COHR latest earnings"))
        self.assertEqual(payload["relevance_score"], 0.88)

    def test_collect_search_evidence_loads_cache_and_summarizes_by_ticker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            ticker_cache = cache_root / "2026-05-07" / "COHR.json"
            ticker_cache.parent.mkdir(parents=True)
            ticker_cache.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "ticker": "COHR",
                                "query": "COHR AI datacenter",
                                "title": "Coherent AI optics demand",
                                "url": "https://example.com/cohr-ai",
                                "published_at": "2026-05-06",
                                "snippet": "AI optics demand remains firm.",
                                "evidence_type": "news",
                                "relevance_score": 0.9,
                                "freshness_hours": 24,
                            },
                            {
                                "ticker": "COHR",
                                "query": "COHR earnings",
                                "title": "Coherent earnings release",
                                "url": "https://investors.coherent.com/results",
                                "published_at": "2026-05-04",
                                "snippet": "Fiscal results improved.",
                                "evidence_type": "earnings",
                                "relevance_score": 0.8,
                                "freshness_hours": 72,
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = collect_search_evidence(
                run_date=date(2026, 5, 7),
                tickers=["COHR", "ALAB"],
                cache_root=cache_root,
                config=SearchEvidenceConfig(mode="cache"),
            )

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["date"], "2026-05-07")
        self.assertEqual(payload["provider"], "cache")
        self.assertEqual(payload["run_summary"]["candidate_ticker_count"], 2)
        self.assertEqual(payload["run_summary"]["cache_hit_count"], 1)
        self.assertEqual(payload["run_summary"]["provider_call_count"], 0)
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["by_ticker"]["COHR"]["evidence_count"], 2)
        self.assertEqual(payload["by_ticker"]["COHR"]["evidence_status"], "covered")
        self.assertEqual(payload["by_ticker"]["COHR"]["provider_status"], "cache_hit")
        self.assertEqual(payload["by_ticker"]["COHR"]["source_diversity"], 2)
        self.assertGreater(payload["by_ticker"]["COHR"]["coverage_score"], 0)
        self.assertEqual(payload["by_ticker"]["ALAB"]["evidence_count"], 0)
        self.assertEqual(payload["by_ticker"]["ALAB"]["evidence_status"], "no_evidence")
        self.assertFalse(payload["by_ticker"]["ALAB"]["priority_for_refresh"])

    def test_collect_search_evidence_reuses_recent_cache_within_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            ticker_cache = cache_root / "2026-05-06" / "COHR.json"
            ticker_cache.parent.mkdir(parents=True)
            ticker_cache.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "ticker": "COHR",
                                "query": "COHR AI datacenter",
                                "title": "Coherent AI optics demand",
                                "url": "https://example.com/cohr-ai",
                                "published_at": "2026-05-06",
                                "snippet": "AI optics demand remains firm.",
                                "evidence_type": "news",
                                "relevance_score": 0.9,
                                "freshness_hours": 24,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = SearchEvidenceConfig(mode="cache", cache_ttl_hours=48)

            payload = collect_search_evidence(
                run_date=date(2026, 5, 7),
                tickers=["COHR"],
                cache_root=cache_root,
                config=config,
            )

        self.assertEqual(payload["run_summary"]["cache_hit_count"], 1)
        self.assertEqual(payload["run_summary"]["stale_cache_hit_count"], 1)
        self.assertEqual(payload["run_summary"]["cache_ttl_hours"], 48)
        self.assertEqual(payload["by_ticker"]["COHR"]["evidence_count"], 1)
        self.assertEqual(payload["by_ticker"]["COHR"]["provider_status"], "cache_hit")
        self.assertEqual(payload["by_ticker"]["COHR"]["cache_source_date"], "2026-05-06")
        self.assertEqual(payload["by_ticker"]["COHR"]["cache_age_hours"], 24)

    def test_collect_search_evidence_ignores_cache_outside_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            ticker_cache = cache_root / "2026-05-05" / "COHR.json"
            ticker_cache.parent.mkdir(parents=True)
            ticker_cache.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "ticker": "COHR",
                                "query": "COHR AI datacenter",
                                "title": "Coherent AI optics demand",
                                "url": "https://example.com/cohr-ai",
                                "published_at": "2026-05-05",
                                "snippet": "AI optics demand remains firm.",
                                "evidence_type": "news",
                                "relevance_score": 0.9,
                                "freshness_hours": 48,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = SearchEvidenceConfig(mode="cache", cache_ttl_hours=24)

            payload = collect_search_evidence(
                run_date=date(2026, 5, 7),
                tickers=["COHR"],
                cache_root=cache_root,
                config=config,
            )

        self.assertEqual(payload["run_summary"]["cache_hit_count"], 0)
        self.assertEqual(payload["run_summary"]["stale_cache_hit_count"], 0)
        self.assertEqual(payload["by_ticker"]["COHR"]["evidence_count"], 0)
        self.assertEqual(payload["by_ticker"]["COHR"]["provider_status"], "not_requested")

    def test_collect_search_evidence_reuses_recent_cache_before_openai_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            ticker_cache = cache_root / "2026-05-06" / "ALAB.json"
            ticker_cache.parent.mkdir(parents=True)
            ticker_cache.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "ticker": "ALAB",
                                "query": "ALAB earnings",
                                "title": "Astera Labs results",
                                "url": "https://example.com/alab",
                                "published_at": "2026-05-06",
                                "snippet": "Recent earnings evidence.",
                                "evidence_type": "earnings",
                                "relevance_score": 0.8,
                                "freshness_hours": 24,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            provider = _FakeSearchProvider()
            config = SearchEvidenceConfig(
                mode="openai",
                model_profile="standard",
                max_search_tickers_per_run=1,
                max_queries_per_ticker=1,
                cache_ttl_hours=48,
                query_templates=("{ticker} latest evidence",),
            )

            payload = collect_search_evidence(
                run_date=date(2026, 5, 7),
                tickers=["ALAB"],
                cache_root=cache_root,
                config=config,
                provider=provider,
            )

        self.assertEqual(provider.calls, [])
        self.assertEqual(payload["provider"], "cache")
        self.assertEqual(payload["run_summary"]["provider_candidate_count"], 0)
        self.assertEqual(payload["run_summary"]["stale_cache_hit_count"], 1)
        self.assertEqual(payload["by_ticker"]["ALAB"]["provider_status"], "cache_hit")
        self.assertEqual(payload["by_ticker"]["ALAB"]["cache_source_date"], "2026-05-06")

    def test_collect_search_evidence_ignores_invalid_cache_and_keeps_valid_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            bad_cache = cache_root / "2026-05-07" / "AAPL.json"
            bad_cache.parent.mkdir(parents=True)
            bad_cache.write_text("{not-json", encoding="utf-8")

            payload = collect_search_evidence(
                run_date=date(2026, 5, 7),
                tickers=["AAPL"],
                cache_root=cache_root,
                config=SearchEvidenceConfig(mode="cache"),
            )

        self.assertEqual(payload["run_summary"]["cache_error_count"], 1)
        self.assertEqual(payload["by_ticker"]["AAPL"]["evidence_count"], 0)
        self.assertEqual(payload["by_ticker"]["AAPL"]["evidence_status"], "cache_error")
        self.assertEqual(payload["items"], [])

    def test_collect_search_evidence_writes_priority_reasons_in_cache_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = collect_search_evidence(
                run_date=date(2026, 5, 7),
                tickers=["AAPL", "AMD"],
                priority_tickers=["AAPL"],
                priority_context_by_ticker={"AAPL": {"action": "avoid", "change_percent": "-6.2%"}},
                cache_root=Path(temp_dir) / "cache",
                config=SearchEvidenceConfig(mode="cache"),
            )

        self.assertEqual(payload["run_summary"]["priority_tickers"], ["AAPL"])
        self.assertEqual(payload["run_summary"]["priority_ticker_count"], 1)
        self.assertEqual(
            payload["by_ticker"]["AAPL"]["priority_refresh_reasons"],
            ["router_selected", "not_refreshed", "important_action", REASON_HIGH_VOLATILITY],
        )
        self.assertEqual(payload["run_summary"]["priority_refresh_reasons"]["not_refreshed"], 1)
        self.assertEqual(payload["run_summary"]["priority_refresh_reasons"]["important_action"], 1)
        self.assertEqual(payload["run_summary"]["priority_refresh_reasons"]["high_volatility"], 1)
        self.assertEqual(payload["run_summary"]["priority_status_counts"], {"no_evidence": 1})
        self.assertEqual(payload["run_summary"]["priority_refresh_candidate_count"], 0)

    def test_collect_search_evidence_reorders_priority_tickers_before_provider_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            ticker_cache = cache_root / "2026-05-06" / "AAPL.json"
            ticker_cache.parent.mkdir(parents=True)
            ticker_cache.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "ticker": "AAPL",
                                "query": "AAPL earnings",
                                "title": "Apple results",
                                "url": "https://example.com/aapl",
                                "published_at": "2026-05-06",
                                "snippet": "Recent earnings evidence.",
                                "evidence_type": "earnings",
                                "relevance_score": 0.8,
                                "freshness_hours": 24,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            provider = _FakeSearchProvider()
            config = SearchEvidenceConfig(
                mode="openai",
                model_profile="standard",
                max_search_tickers_per_run=1,
                max_queries_per_ticker=1,
                cache_ttl_hours=48,
                query_templates=("{ticker} latest evidence",),
            )

            payload = collect_search_evidence(
                run_date=date(2026, 5, 7),
                tickers=["AAPL", "AMD", "COHR"],
                priority_tickers=["AAPL", "AMD", "COHR"],
                priority_context_by_ticker={
                    "AAPL": {"in_portfolio": True},
                    "AMD": {"action": "buy", "change_percent": 8.5},
                    "COHR": {"action": "watch"},
                },
                cache_root=cache_root,
                config=config,
                provider=provider,
            )

        self.assertEqual(provider.calls, [("AMD", ["AMD latest evidence"])])
        self.assertEqual(payload["run_summary"]["priority_tickers"], ["AMD", "COHR", "AAPL"])
        self.assertEqual(payload["run_summary"]["priority_refresh_candidate_count"], 1)
        self.assertEqual(
            payload["by_ticker"]["AAPL"]["priority_refresh_reasons"],
            ["router_selected", "stale_cache", "portfolio_holding"],
        )
        self.assertEqual(payload["by_ticker"]["AMD"]["evidence_status"], "covered")
        self.assertEqual(payload["by_ticker"]["COHR"]["evidence_status"], "not_refreshed")

    def test_build_search_evidence_payload_emits_empty_valid_shape(self) -> None:
        payload = build_search_evidence_payload(
            run_date=date(2026, 5, 7),
            tickers=["AAPL"],
            items=[],
            cache_hit_count=0,
            cache_error_count=0,
        )

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["date"], "2026-05-07")
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["by_ticker"]["AAPL"]["coverage_score"], 0.0)
        self.assertEqual(payload["by_ticker"]["AAPL"]["evidence_status"], "no_evidence")
        self.assertEqual(payload["by_ticker"]["AAPL"]["provider_status"], "not_requested")
        self.assertEqual(payload["run_summary"]["searched_ticker_count"], 0)

    def test_build_search_evidence_payload_lists_priority_tickers_in_summary(self) -> None:
        payload = build_search_evidence_payload(
            run_date=date(2026, 5, 7),
            tickers=["COHR", "ALAB"],
            items=[],
            cache_hit_count=0,
            cache_error_count=0,
            priority_tickers=[" alab ", "MISSING", "ALAB"],
        )

        self.assertEqual(payload["run_summary"]["priority_tickers"], ["ALAB"])
        self.assertEqual(payload["run_summary"]["priority_ticker_count"], 1)
        self.assertFalse(payload["by_ticker"]["COHR"]["priority_for_refresh"])
        self.assertTrue(payload["by_ticker"]["ALAB"]["priority_for_refresh"])

    def test_build_search_evidence_payload_counts_priority_reason_and_status_maps(self) -> None:
        payload = build_search_evidence_payload(
            run_date=date(2026, 5, 7),
            tickers=["COHR", "ALAB"],
            items=[],
            cache_hit_count=0,
            cache_error_count=0,
            mode="openai",
            priority_tickers=["ALAB"],
            priority_refresh_reasons={"ALAB": ["router_selected", "no_evidence"]},
            provider_candidate_tickers={"ALAB"},
            provider_attempted_tickers={"ALAB"},
        )

        self.assertEqual(
            payload["run_summary"]["priority_refresh_reasons"],
            {"no_evidence": 1, "router_selected": 1},
        )
        self.assertEqual(payload["run_summary"]["priority_status_counts"], {"no_evidence": 1})
        self.assertEqual(payload["run_summary"]["priority_refresh_candidate_count"], 1)
        self.assertEqual(
            payload["by_ticker"]["ALAB"]["priority_refresh_reasons"],
            ["router_selected", "no_evidence"],
        )
        self.assertEqual(payload["by_ticker"]["COHR"]["priority_refresh_reasons"], [])

    def test_build_search_evidence_payload_ignores_reasons_for_non_priority_tickers(self) -> None:
        payload = build_search_evidence_payload(
            run_date=date(2026, 5, 7),
            tickers=["COHR", "ALAB"],
            items=[],
            cache_hit_count=0,
            cache_error_count=0,
            priority_tickers=["ALAB"],
            priority_refresh_reasons={
                "COHR": ["should_not_attach"],
                "ALAB": ["router_selected"],
            },
        )

        self.assertFalse(payload["by_ticker"]["COHR"]["priority_for_refresh"])
        self.assertEqual(payload["by_ticker"]["COHR"]["priority_refresh_reasons"], [])
        self.assertEqual(payload["by_ticker"]["ALAB"]["priority_refresh_reasons"], ["router_selected"])
        self.assertEqual(payload["run_summary"]["priority_refresh_reasons"], {"router_selected": 1})

    def test_collect_search_evidence_uses_openai_provider_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            provider = _FakeSearchProvider()
            config = SearchEvidenceConfig(
                mode="openai",
                model_profile="standard",
                max_search_tickers_per_run=1,
                max_queries_per_ticker=1,
                query_templates=("{ticker} latest evidence",),
            )

            with patch("src.collector.search_evidence.record_pipeline_event") as record_event:
                payload = collect_search_evidence(
                    run_date=date(2026, 5, 7),
                    tickers=["COHR", "ALAB"],
                    priority_tickers=["ALAB"],
                    cache_root=cache_root,
                    config=config,
                    provider=provider,
                )

            cache_payload = json.loads((cache_root / "2026-05-07" / "ALAB.json").read_text(encoding="utf-8"))

        self.assertEqual(provider.calls, [("ALAB", ["ALAB latest evidence"])])
        self.assertEqual(payload["provider"], "openai")
        self.assertEqual(payload["run_summary"]["provider_call_count"], 1)
        self.assertEqual(payload["run_summary"]["priority_ticker_count"], 1)
        self.assertEqual(payload["run_summary"]["skipped_ticker_count"], 1)
        self.assertEqual(payload["by_ticker"]["COHR"]["evidence_count"], 0)
        self.assertEqual(payload["by_ticker"]["COHR"]["evidence_status"], "not_refreshed")
        self.assertEqual(payload["by_ticker"]["ALAB"]["evidence_count"], 1)
        self.assertEqual(payload["by_ticker"]["ALAB"]["evidence_status"], "covered")
        self.assertTrue(payload["by_ticker"]["ALAB"]["priority_for_refresh"])
        self.assertEqual(cache_payload["items"][0]["ticker"], "ALAB")
        self.assertTrue(any(call.args[2] == "budget_guard_decision" for call in record_event.call_args_list))

    def test_collect_search_evidence_marks_provider_unavailable_for_priority_tickers(self) -> None:
        config = SearchEvidenceConfig(
            mode="openai",
            model_profile="standard",
            max_search_tickers_per_run=1,
            max_queries_per_ticker=1,
            query_templates=("{ticker} latest evidence",),
        )

        with patch.dict("os.environ", {}, clear=True):
            payload = collect_search_evidence(
                run_date=date(2026, 5, 7),
                tickers=["COHR", "ALAB"],
                priority_tickers=["ALAB"],
                cache_root=Path(tempfile.gettempdir()) / "unused-search-evidence-cache",
                config=config,
                provider=None,
            )

        self.assertEqual(payload["by_ticker"]["ALAB"]["evidence_status"], "provider_unavailable")
        self.assertEqual(payload["by_ticker"]["ALAB"]["provider_status"], "provider_unavailable")
        self.assertEqual(payload["by_ticker"]["COHR"]["evidence_status"], "not_refreshed")
        self.assertEqual(payload["run_summary"]["status_counts"]["provider_unavailable"], 1)

    def test_collect_search_evidence_marks_provider_error_per_ticker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = SearchEvidenceConfig(
                mode="openai",
                model_profile="standard",
                max_search_tickers_per_run=1,
                max_queries_per_ticker=1,
                query_templates=("{ticker} latest evidence",),
            )

            payload = collect_search_evidence(
                run_date=date(2026, 5, 7),
                tickers=["ALAB"],
                priority_tickers=["ALAB"],
                cache_root=Path(temp_dir) / "cache",
                config=config,
                provider=_FailingSearchProvider(),
            )

        self.assertEqual(payload["run_summary"]["provider_error_count"], 1)
        self.assertEqual(payload["by_ticker"]["ALAB"]["evidence_status"], "provider_error")
        self.assertEqual(payload["by_ticker"]["ALAB"]["provider_status"], "provider_error")

    def test_collect_search_evidence_skips_provider_when_budget_guard_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = _FakeSearchProvider()
            config = SearchEvidenceConfig(
                mode="openai",
                model_profile="standard",
                max_search_tickers_per_run=1,
                max_queries_per_ticker=1,
                query_templates=("{ticker} latest evidence",),
            )
            budget_config = BudgetGuardConfig(
                mode="enforce",
                daily_cap_usd=0.0,
                guarded_profiles=("standard",),
                guarded_paths=("search_evidence",),
            )

            with patch("src.collector.search_evidence.load_budget_guard_config", return_value=budget_config):
                payload = collect_search_evidence(
                    run_date=date(2026, 5, 7),
                    tickers=["COHR"],
                    cache_root=Path(temp_dir) / "cache",
                    config=config,
                    provider=provider,
                )

        self.assertEqual(provider.calls, [])
        self.assertEqual(payload["provider"], "cache")
        self.assertEqual(payload["run_summary"]["provider_call_count"], 0)
        self.assertEqual(payload["run_summary"]["skipped_ticker_count"], 1)

    def test_write_search_evidence_output_writes_and_syncs_web_public_copy(self) -> None:
        from src.output.search_evidence_json import write_search_evidence_output

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "web" / "public" / "output" / "data").mkdir(parents=True)
            payload = build_search_evidence_payload(
                run_date=date(2026, 5, 7),
                tickers=["COHR"],
                items=[
                    SearchEvidenceItem(
                        ticker="COHR",
                        query="COHR earnings",
                        title="Coherent results",
                        url="https://example.com/cohr",
                    )
                ],
                cache_hit_count=1,
                cache_error_count=0,
            )

            path = write_search_evidence_output(payload, output_root=root / "output")

            source = json.loads(path.read_text(encoding="utf-8"))
            mirror = json.loads(
                (root / "web" / "public" / "output" / "data" / "search_evidence.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(path, root / "output" / "data" / "search_evidence.json")
        self.assertEqual(source["schema_version"], 1)
        self.assertEqual(source, mirror)

    def test_write_search_evidence_output_raises_json_write_error_for_invalid_payload(self) -> None:
        from src.output.json_writer import JsonWriteError
        from src.output.search_evidence_json import write_search_evidence_output

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            with self.assertRaises(JsonWriteError):
                write_search_evidence_output({"bad": object()}, output_root=root / "output")

            self.assertFalse((root / "output" / "data" / "search_evidence.json").exists())
