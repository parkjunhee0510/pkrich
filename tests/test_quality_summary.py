from __future__ import annotations

import unittest

from src.analyzer.quality_summary import build_quality_summary, select_quality_summary_by_source


class TestQualitySummary(unittest.TestCase):
    def test_build_quality_summary_aggregates_validation_details(self) -> None:
        summary = build_quality_summary(
            {
                "validation_details": {
                    "AAPL": {
                        "counts": {
                            "fact_warning": 2,
                            "hallucination_warning": 1,
                            "consistency_warning": 3,
                        },
                        "warnings": [
                            {"category": "schema_violation", "field": "summary", "message": "encoding issue detected"},
                            {"category": "schema_violation", "field": "signal_or_takeaway", "message": "contains replacement char \ufffd"},
                        ],
                    }
                },
                "fallback_used": True,
            }
        )

        self.assertEqual(
            summary["AAPL"],
            {
                "fact_warning_count": 2,
                "hallucination_warning_count": 1,
                "consistency_warning_count": 3,
                "fallback_used": True,
                "encoding_issue_detected": True,
            },
        )

    def test_build_quality_summary_creates_fallback_entries_without_validation_details(self) -> None:
        summary = build_quality_summary(
            {"fallback_reason": "missing_openai_key"},
            tickers=["AAPL", "MSFT"],
        )

        self.assertEqual(
            summary,
            {
                "AAPL": {
                    "fact_warning_count": 0,
                    "hallucination_warning_count": 0,
                    "consistency_warning_count": 0,
                    "fallback_used": True,
                    "encoding_issue_detected": False,
                },
                "MSFT": {
                    "fact_warning_count": 0,
                    "hallucination_warning_count": 0,
                    "consistency_warning_count": 0,
                    "fallback_used": True,
                    "encoding_issue_detected": False,
                },
            },
        )

    def test_select_quality_summary_by_source_uses_selected_path_precedence(self) -> None:
        selected = select_quality_summary_by_source(
            tickers=["AAPL", "MSFT", "NVDA"],
            economy_summary_by_ticker={
                "AAPL": {"fact_warning_count": 1, "fallback_used": False},
                "MSFT": {"fact_warning_count": 2, "fallback_used": False},
                "NVDA": {"fact_warning_count": 3, "fallback_used": False},
            },
            deep_summary_by_ticker={
                "AAPL": {"hallucination_warning_count": 1, "fallback_used": True},
                "MSFT": {"hallucination_warning_count": 2, "fallback_used": False},
            },
            tie_break_summary_by_ticker={
                "AAPL": {"consistency_warning_count": 1, "fallback_used": False},
            },
            selected_source_by_ticker={
                "AAPL": "tie_break",
                "MSFT": "deep",
                "NVDA": "economy",
            },
        )

        self.assertEqual(selected["AAPL"], {"consistency_warning_count": 1, "fallback_used": False})
        self.assertEqual(selected["MSFT"], {"hallucination_warning_count": 2, "fallback_used": False})
        self.assertEqual(selected["NVDA"], {"fact_warning_count": 3, "fallback_used": False})


if __name__ == "__main__":
    unittest.main()
