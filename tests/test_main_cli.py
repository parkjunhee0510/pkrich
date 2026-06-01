from __future__ import annotations

import unittest
from unittest.mock import patch

import main as entrypoint


class MainCliTests(unittest.TestCase):
    def test_default_run_forwards_with_sectors_false(self) -> None:
        with (
            patch.object(entrypoint, "_check_dependencies"),
            patch("src.pipeline.collect_only") as collect_only,
            patch("src.pipeline.run_pipeline") as run_pipeline,
        ):
            entrypoint.main([])

        collect_only.assert_not_called()
        run_pipeline.assert_called_once_with(with_sectors=False, show_progress=True)

    def test_with_sectors_flag_forwards_true(self) -> None:
        with (
            patch.object(entrypoint, "_check_dependencies"),
            patch("src.pipeline.collect_only") as collect_only,
            patch("src.pipeline.run_pipeline") as run_pipeline,
        ):
            entrypoint.main(["--with-sectors"])

        collect_only.assert_not_called()
        run_pipeline.assert_called_once_with(with_sectors=True, show_progress=True)

    def test_collect_only_wins_over_with_sectors(self) -> None:
        with (
            patch.object(entrypoint, "_check_dependencies"),
            patch("src.pipeline.collect_only") as collect_only,
            patch("src.pipeline.run_pipeline") as run_pipeline,
        ):
            entrypoint.main(["--collect-only", "--with-sectors"])

        collect_only.assert_called_once_with(show_progress=True)
        run_pipeline.assert_not_called()

    def test_no_progress_flag_disables_cli_progress(self) -> None:
        with (
            patch.object(entrypoint, "_check_dependencies"),
            patch("src.pipeline.collect_only") as collect_only,
            patch("src.pipeline.run_pipeline") as run_pipeline,
        ):
            entrypoint.main(["--no-progress"])

        collect_only.assert_not_called()
        run_pipeline.assert_called_once_with(with_sectors=False, show_progress=False)


if __name__ == "__main__":
    unittest.main()
