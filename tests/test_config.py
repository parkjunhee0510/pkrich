from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.utils.config import load_watchlist


class LoadWatchlistTests(unittest.TestCase):
    def test_load_watchlist_reads_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "watchlist.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "watchlist:",
                        "  - ticker: AAPL",
                        "    name: Apple Inc.",
                        '    sector: Technology',
                        '    keywords: ["iPhone", "AI"]',
                    ]
                ),
                encoding="utf-8",
            )

            items = load_watchlist(str(config_path))

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].ticker, "AAPL")
            self.assertEqual(items[0].name, "Apple Inc.")
            self.assertEqual(items[0].sector, "Technology")
            self.assertEqual(items[0].keywords, ["iPhone", "AI"])


if __name__ == "__main__":
    unittest.main()
