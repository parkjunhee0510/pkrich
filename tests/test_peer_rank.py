from __future__ import annotations

import unittest

from src.analyzer.peer_rank import build_peer_rank


class PeerRankTests(unittest.TestCase):
    def test_lower_pe_is_better(self) -> None:
        peer_rank = build_peer_rank(
            company_metrics={"pe_ratio": "18.0x"},
            peer_metrics=[
                {"pe_ratio": "20.0x"},
                {"pe_ratio": "24.0x"},
                {"pe_ratio": "30.0x"},
            ],
        )
        self.assertEqual(peer_rank["per_pctl"], 75)

    def test_higher_quality_and_momentum_metrics_are_better(self) -> None:
        peer_rank = build_peer_rank(
            company_metrics={
                "price_change_30d": "+10.0%",
                "roe": "24.0%",
                "revenue_growth": "+18.0%",
            },
            peer_metrics=[
                {"price_change_30d": "+6.0%", "roe": "22.0%", "revenue_growth": "+12.0%"},
                {"price_change_30d": "+2.0%", "roe": "18.0%", "revenue_growth": "+10.0%"},
                {"price_change_30d": "-1.0%", "roe": "12.0%", "revenue_growth": "+4.0%"},
            ],
        )
        self.assertEqual(peer_rank["rs_pctl"], 75)
        self.assertEqual(peer_rank["roe_pctl"], 75)
        self.assertEqual(peer_rank["revenue_growth_pctl"], 75)

    def test_ties_share_same_percentile(self) -> None:
        peer_rank = build_peer_rank(
            company_metrics={"price_change_30d": "+6.0%"},
            peer_metrics=[
                {"price_change_30d": "+6.0%"},
                {"price_change_30d": "+2.0%"},
                {"price_change_30d": "-2.0%"},
            ],
        )
        self.assertEqual(peer_rank["rs_pctl"], 50)

    def test_returns_empty_payload_when_data_is_insufficient(self) -> None:
        peer_rank = build_peer_rank(
            company_metrics={"pe_ratio": "18.0x"},
            peer_metrics=[{"pe_ratio": "20.0x"}],
        )
        self.assertEqual(peer_rank, {})

    def test_builds_korean_summary(self) -> None:
        peer_rank = build_peer_rank(
            company_metrics={
                "pe_ratio": "15.0x",
                "price_change_30d": "+12.0%",
                "roe": "15.0%",
            },
            peer_metrics=[
                {"pe_ratio": "18.0x", "price_change_30d": "+7.0%", "roe": "13.0%"},
                {"pe_ratio": "22.0x", "price_change_30d": "+4.0%", "roe": "12.0%"},
                {"pe_ratio": "25.0x", "price_change_30d": "+1.0%", "roe": "11.0%"},
            ],
        )
        self.assertIn("PER", peer_rank["summary"])
        self.assertIn("모멘텀", peer_rank["summary"])


if __name__ == "__main__":
    unittest.main()
