from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.cli import run_sectors
from src.utils.config import SectorConfig, SectorTickerConfig


class RunSectorsCliTests(unittest.TestCase):
    def test_main_sanitizes_broken_proxy_before_scan(self) -> None:
        proxy_names = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]
        original = {name: os.environ.get(name) for name in proxy_names}
        try:
            for name in proxy_names:
                os.environ[name] = "http://127.0.0.1:9"

            sector = SectorConfig(
                id="cloud_software",
                name="Cloud Software",
                tickers=[SectorTickerConfig(ticker="MSFT", name="Microsoft")],
            )
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "sectors.json"
                output_path.write_text("{}", encoding="utf-8")

                with (
                    patch.object(
                        sys,
                        "argv",
                        ["run_sectors", "--date", "2026-05-26", "--no-sync"],
                    ),
                    patch("src.cli.run_sectors.load_sectors", return_value=[sector]),
                    patch("src.cli.run_sectors.load_watchlist", return_value=[]),
                    patch("src.cli.run_sectors.scan_sectors", return_value=[]),
                    patch(
                        "src.cli.run_sectors.write_sectors_json",
                        return_value=output_path,
                    ),
                    patch("src.cli.run_sectors.record_pipeline_event"),
                ):
                    run_sectors.main()

            for name in proxy_names:
                self.assertIsNone(os.environ.get(name))
        finally:
            for name, value in original.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
