from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.pipeline import run_pipeline


class PipelineTests(unittest.TestCase):
    def test_run_pipeline_writes_expected_outputs_in_fallback_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_dir = temp_path / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "watchlist.yaml").write_text(
                "\n".join(
                    [
                        "watchlist:",
                        "  - ticker: AAPL",
                        "    name: Apple Inc.",
                        "    sector: Technology",
                        '    keywords: ["iPhone", "AI"]',
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"ENABLE_EXTERNAL_FETCH": "false"}, clear=False):
                current_dir = os.getcwd()
                try:
                    os.chdir(temp_path)
                    run_pipeline(run_date=date(2026, 4, 8))
                finally:
                    os.chdir(current_dir)

            daily_path = temp_path / "output" / "daily" / "2026-04-08.md"
            ticker_path = temp_path / "output" / "tickers" / "AAPL" / "2026-04-08.md"
            csv_path = temp_path / "output" / "data" / "price_history.csv"

            self.assertTrue(daily_path.exists())
            self.assertTrue(ticker_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertIn("AAPL", daily_path.read_text(encoding="utf-8"))
            self.assertIn("External fetch disabled", ticker_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
