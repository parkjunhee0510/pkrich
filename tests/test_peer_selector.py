from __future__ import annotations

import unittest

from src.analyzer.peer_selector import PeerSelector


class PeerSelectorTests(unittest.TestCase):
    def test_filters_by_market_cap_band_and_prefers_data_coverage(self) -> None:
        selector = PeerSelector()
        peers = selector.select_peers(
            "AAPL",
            "Technology",
            "1000",
            [
                {"ticker": "MSFT", "market_cap": "1100", "pe_ratio": "30x", "roe": "20%", "gross_margin": "40%", "avg_volume": "100"},
                {"ticker": "GOOG", "market_cap": "900", "pe_ratio": "25x", "avg_volume": "90"},
                {"ticker": "SMALL", "market_cap": "400", "pe_ratio": "18x", "avg_volume": "1000"},
                {"ticker": "NVDA", "market_cap": "1200", "pe_ratio": "35x", "roe": "25%", "gross_margin": "60%", "avg_volume": "95", "rs_vs_spy": "+5%"},
            ],
        )
        self.assertEqual([peer.ticker for peer in peers[:3]], ["NVDA", "MSFT", "GOOG"])
        self.assertNotIn("SMALL", [peer.ticker for peer in peers])

    def test_backfills_when_size_filtered_pool_is_too_small(self) -> None:
        selector = PeerSelector()
        peers = selector.select_peers(
            "AAPL",
            "Technology",
            "1000",
            [
                {"ticker": "MSFT", "market_cap": "1100", "pe_ratio": "30x"},
                {"ticker": "FAR1", "market_cap": "3000", "pe_ratio": "20x", "roe": "22%"},
                {"ticker": "FAR2", "market_cap": "3500", "pe_ratio": "18x", "roe": "19%"},
            ],
        )
        self.assertEqual(len(peers), 3)
        self.assertEqual(peers[0].ticker, "MSFT")


if __name__ == "__main__":
    unittest.main()
