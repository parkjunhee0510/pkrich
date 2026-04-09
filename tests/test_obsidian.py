from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.output.obsidian import mirror_markdown_outputs


class ObsidianSyncTests(unittest.TestCase):
    def test_mirror_markdown_outputs_skips_when_path_is_unset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            daily_path = temp_path / "2026-04-08.md"
            ticker_path = temp_path / "AAPL.md"
            daily_path.write_text("daily", encoding="utf-8")
            ticker_path.write_text("ticker", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("OBSIDIAN_VAULT_PATH", None)
                mirror_markdown_outputs(daily_path, {"AAPL": ticker_path})

            self.assertFalse((temp_path / "pkrich").exists())

    def test_mirror_markdown_outputs_logs_warning_when_copy_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            daily_path = temp_path / "2026-04-08.md"
            ticker_path = temp_path / "AAPL.md"
            daily_path.write_text("daily", encoding="utf-8")
            ticker_path.write_text("ticker", encoding="utf-8")

            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": str(temp_path / "vault")}, clear=False):
                with patch("src.output.obsidian.shutil.copy2", side_effect=PermissionError("blocked")):
                    with patch("src.output.obsidian.logger.warning") as warning_mock:
                        mirror_markdown_outputs(daily_path, {"AAPL": ticker_path})

            self.assertEqual(warning_mock.call_count, 2)
            self.assertIn("obsidian_sync_failed", warning_mock.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
