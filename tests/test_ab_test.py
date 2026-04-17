from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from src.analyzer.ab_test import ABTestRunner, build_weekly_ab_test_payload
from src.analyzer.base import ModuleResult
from src.analyzer.prompts.base import PromptTemplate
from src.output.ab_test import write_ab_test_results
from src.types import CollectedTickerData, NewsItem, TickerAnalysis, WatchlistItem


def _watchlist(count: int = 6) -> list[WatchlistItem]:
    return [WatchlistItem(ticker=f"T{i}", name=f"Ticker {i}", sector="Technology") for i in range(1, count + 1)]


def _collected(ticker: str) -> CollectedTickerData:
    return CollectedTickerData(
        ticker=ticker,
        name=ticker,
        sector="Technology",
        price=100.0,
        change_percent=1.0,
        currency="USD",
        market_cap="10.0B",
        pe_ratio="20.0",
        summary_note="sample",
    )


def _analysis(ticker: str) -> TickerAnalysis:
    return TickerAnalysis(
        ticker=ticker,
        name=ticker,
        date="2026-04-19",
        summary="요약 문장 하나입니다. 요약 문장 둘입니다.",
        key_news=["샘플 뉴스"],
        news_references=[NewsItem(title="Sample headline", source="Reuters", published_at="2026-04-18", link="https://example.com")],
        financial_highlights=["매출 +10.0%"],
        risks_or_watchpoints=["100 USD 하향 이탈 주의"],
        signal_or_takeaway="매수 관찰 — 실적 기대 | 진입 트리거 101 돌파 | 목표 110/115 | 손절 97",
        data_snapshot={"Price": "100.00 USD", "Daily Change": "+1.00%", "Sector": "Technology"},
        fundamentals={"market_cap": "10.0B"},
        price_action={"atr_14d": "3.0"},
        quarterly_financials=[],
        upcoming_events=[],
        news_tone={"label": "bullish", "score": 1},
        trade_frame={"base_scenario": "실적 기대 유지"},
    )


def _template(version: str) -> PromptTemplate:
    return PromptTemplate(
        name="signal_takeaway_module",
        version=version,
        system_template="system",
        user_template="{batch_payload_json}",
        output_schema={"type": "object"},
    )


class ABTestTests(unittest.TestCase):
    def test_select_weekly_sample_is_deterministic(self) -> None:
        watchlist = _watchlist()
        runner = ABTestRunner(
            run_date=date(2026, 4, 19),
            watchlist=watchlist,
            collected={item.ticker: _collected(item.ticker) for item in watchlist},
            news_map={item.ticker: [] for item in watchlist},
            analyses=[_analysis(item.ticker) for item in watchlist],
        )

        first = runner.select_weekly_sample(sample_size=5)
        second = runner.select_weekly_sample(sample_size=5)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 5)

    def test_run_test_compares_two_variants(self) -> None:
        watchlist = _watchlist(2)
        signal_csv_dir = tempfile.TemporaryDirectory()
        signal_csv_path = Path(signal_csv_dir.name) / "signal_tracker.csv"
        signal_csv_path.write_text(
            "\n".join(
                [
                    "signal_date,ticker,signal_type,signal_direction,signal_price,catalyst_tag,news_tone,trade_frame_scenario,return_1d,return_5d,return_20d,evaluated_1d,evaluated_5d,evaluated_20d",
                    "2026-04-01,T1,takeaway,bull,100,tag,bullish,base,+1.0%,+5.0%,N/A,True,True,False",
                    "2026-04-01,T2,takeaway,bear,100,tag,bearish,base,-1.0%,-3.0%,N/A,True,True,False",
                ]
            ),
            encoding="utf-8",
        )

        def executor(module, ctx, prompt_template):
            del module
            payload = {}
            details = {}
            for item in ctx.watchlist:
                if prompt_template.version == "research_v1":
                    text = "매수 관찰 — 촉매 | 진입 트리거 101 돌파 | 목표 110/115 | 손절 97"
                    warning_count = 0
                else:
                    text = "매도 경계 — 리스크 | 진입 트리거 99 이탈 | 목표 95/90 | 손절 103"
                    warning_count = 1
                payload[item.ticker] = {"signal_or_takeaway": text}
                details[item.ticker] = {"warning_count": warning_count, "counts": {"schema_violation": warning_count}, "warnings": []}
            return ModuleResult(results_by_ticker=payload, diagnostics={"validation_details": details})

        runner = ABTestRunner(
            run_date=date(2026, 4, 19),
            watchlist=watchlist,
            collected={item.ticker: _collected(item.ticker) for item in watchlist},
            news_map={item.ticker: [] for item in watchlist},
            analyses=[_analysis(item.ticker) for item in watchlist],
            signal_csv_path=signal_csv_path,
            variant_executor=executor,
        )

        payload = runner.run_test(["T1", "T2"], _template("research_v1"), _template("research_v2"))
        signal_csv_dir.cleanup()

        self.assertEqual(payload["status"], "executed")
        self.assertEqual(payload["module"], "signal_takeaway_module")
        self.assertEqual(len(payload["results"]), 2)
        self.assertIn(payload["results"][0]["preferred_variant"], {"a", "b", "tie"})
        self.assertIn("variant_a_avg_fact_accuracy", payload["summary"])

    def test_build_weekly_ab_test_payload_skips_non_sunday(self) -> None:
        watchlist = _watchlist(2)
        payload = build_weekly_ab_test_payload(
            run_date=date(2026, 4, 16),
            watchlist=watchlist,
            collected={item.ticker: _collected(item.ticker) for item in watchlist},
            news_map={item.ticker: [] for item in watchlist},
            analyses=[_analysis(item.ticker) for item in watchlist],
            variant_a=_template("research_v1"),
            variant_b=_template("research_v2"),
        )

        self.assertEqual(payload["status"], "skipped")
        self.assertEqual(payload["reason"], "not_sunday")

    def test_write_ab_test_results_creates_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            project_web = Path(temp_dir) / "web"
            project_web.mkdir(parents=True, exist_ok=True)
            payload = {"status": "executed", "results": []}

            path = write_ab_test_results(payload, output_root=output_root)

            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], "executed")


if __name__ == "__main__":
    unittest.main()
