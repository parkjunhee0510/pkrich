from __future__ import annotations

import unittest
from unittest.mock import patch

from src.analyzer.payloads import build_raw_payloads
from src.analyzer.research_note import _build_payload
from src.types import CollectedTickerData, WatchlistItem
from src.utils.token_estimator import estimate_batch_tokens


def _watchlist() -> list[WatchlistItem]:
    return [
        WatchlistItem(
            ticker="AAPL",
            name="Apple Inc.",
            sector="Technology",
            keywords=["consumer electronics", "hardware", "services", "AI", "wearables"],
        )
    ]


def _collected() -> dict[str, CollectedTickerData]:
    noisy_blob = "FMP raw attachment " * 160
    return {
        "AAPL": CollectedTickerData(
            ticker="AAPL",
            name="Apple Inc.",
            sector="Technology",
            price=210.0,
            change_percent=1.2,
            currency="USD",
            market_cap="3.0T",
            pe_ratio="28.0",
            summary_note="",
            fundamental_metrics={
                "industry": "Consumer Electronics",
                "roe": "31.2%",
                "roic": "22.8%",
                "gross_margin": "45.5%",
                "gross_margin_trend": "improving",
                "operating_margin": "30.1%",
                "operating_margin_trend": "stable",
                "current_ratio": "0.98",
                "debt_to_equity": "1.45",
                "fcf_yield": "3.9%",
                "net_debt_to_ebitda": "0.8x",
                "annual_dividend": "$1.04",
                "dividend_5y_cagr": "5.7%",
                "consecutive_increase_years": "12",
                "beta": "1.18",
                "raw_fmp_profile": noisy_blob,
                "full_financial_statement": noisy_blob,
                "unused_nested_payload": {"raw": noisy_blob},
            },
        )
    }


class AnalyzerPayloadCompactionTests(unittest.TestCase):
    def test_raw_payload_compacts_fmp_fundamental_metrics(self) -> None:
        watchlist = _watchlist()
        collected = _collected()

        raw_payload = build_raw_payloads(watchlist, collected, {})["AAPL"]

        metrics = raw_payload["fundamental_metrics"]
        self.assertEqual(metrics["industry"], "Consumer Electronics")
        self.assertEqual(metrics["roe"], "31.2%")
        self.assertEqual(metrics["gross_margin_trend"], "improving")
        self.assertNotIn("raw_fmp_profile", metrics)
        self.assertNotIn("full_financial_statement", metrics)
        self.assertNotIn("unused_nested_payload", metrics)
        self.assertLessEqual(len(metrics), 16)

        verbose_payload = dict(raw_payload)
        verbose_payload["fundamental_metrics"] = collected["AAPL"].fundamental_metrics
        self.assertLess(
            estimate_batch_tokens([raw_payload]) + 250,
            estimate_batch_tokens([verbose_payload]),
        )

    def test_legacy_research_payload_uses_same_compacted_metrics(self) -> None:
        watchlist = _watchlist()
        collected = _collected()

        with patch.dict("os.environ", {"FINNHUB_API_KEY": "", "FMP_API_KEY": ""}, clear=False):
            legacy_payload = _build_payload(watchlist, collected, {})[0]

        metrics = legacy_payload["fundamental_metrics"]
        self.assertEqual(metrics["industry"], "Consumer Electronics")
        self.assertEqual(metrics["operating_margin_trend"], "stable")
        self.assertNotIn("raw_fmp_profile", metrics)
        self.assertNotIn("full_financial_statement", metrics)


if __name__ == "__main__":
    unittest.main()
