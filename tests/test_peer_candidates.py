from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.collector.peer_candidates import load_peer_candidates, persist_peer_selections
from src.types import CollectedTickerData, WatchlistItem
from src.utils.datastore import get_datastore


def _collected(ticker: str) -> CollectedTickerData:
    return CollectedTickerData(
        ticker=ticker,
        name=ticker,
        sector="Technology",
        price=100.0,
        change_percent=1.0,
        currency="USD",
        market_cap="1000",
        pe_ratio="20.0x",
        summary_note="",
    )


class PeerCandidatesTests(unittest.TestCase):
    def test_load_peer_candidates_prefers_monthly_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            datastore = get_datastore(output_root=output_root, backend="sqlite")
            datastore.set_peer_selection_cache(
                "AAPL",
                "2026-04",
                {
                    "selected_peers": [
                        {"ticker": "MSFT", "market_cap": "1100", "data_coverage_score": 4.0},
                        {"ticker": "GOOG", "market_cap": "900", "data_coverage_score": 3.0},
                    ],
                    "source": "finnhub",
                },
            )

            candidates = load_peer_candidates(
                [WatchlistItem(ticker="AAPL", name="Apple", sector="Technology")],
                {"AAPL": _collected("AAPL")},
                date(2026, 4, 16),
                output_root=output_root,
                datastore=datastore,
            )

            self.assertEqual(len(candidates["AAPL"]), 2)
            self.assertEqual(candidates["AAPL"][0]["ticker"], "MSFT")

    def test_persist_peer_selections_writes_to_monthly_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            datastore = get_datastore(output_root=output_root, backend="sqlite")

            persist_peer_selections(
                {
                    "module_diagnostics": {
                        "peer_comparison_module": {
                            "selected_peers_by_ticker": {
                                "AAPL": {
                                    "selected_peers": [{"ticker": "MSFT", "market_cap": "1100"}],
                                    "source": "finnhub",
                                }
                            }
                        }
                    }
                },
                date(2026, 4, 16),
                output_root=output_root,
                datastore=datastore,
            )

            loaded = datastore.get_peer_selection_cache("AAPL", "2026-04")
            assert loaded is not None
            self.assertEqual(loaded["selected_peers"][0]["ticker"], "MSFT")

    def test_persist_peer_selections_skips_all_na_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            datastore = get_datastore(output_root=output_root, backend="sqlite")

            persist_peer_selections(
                {
                    "module_diagnostics": {
                        "peer_comparison_module": {
                            "selected_peers_by_ticker": {
                                "AAPL": {
                                    "selected_peers": [
                                        {
                                            "ticker": "MSFT",
                                            "pe_ratio": "N/A",
                                            "roe": "N/A",
                                            "gross_margin": "N/A",
                                            "market_cap": "N/A",
                                            "price_change_30d": "N/A",
                                        }
                                    ],
                                    "source": "finnhub",
                                }
                            }
                        }
                    }
                },
                date(2026, 4, 16),
                output_root=output_root,
                datastore=datastore,
            )

            self.assertIsNone(datastore.get_peer_selection_cache("AAPL", "2026-04"))


if __name__ == "__main__":
    unittest.main()
