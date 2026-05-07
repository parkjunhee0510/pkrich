import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from src.output.health_check import check_output_health


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class OutputHealthCheckTests(unittest.TestCase):
    def test_detects_invalid_source_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            source.mkdir(parents=True)
            mirror.mkdir(parents=True)
            (source / "index.json").write_text('{"schema_version": ', encoding="utf-8")

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("invalid_json", {issue.code for issue in result.issues})

    def test_detects_web_public_mirror_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "index.json", {"schema_version": 1, "tickers": []})
            _write_json(root / "web" / "public" / "output" / "data" / "index.json", {"schema_version": 1, "tickers": ["AAPL"]})

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("mirror_mismatch", {issue.code for issue in result.issues})

    def test_detects_missing_ticker_mirror_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "tickers" / "AAPL" / "latest.json", {"ticker": "AAPL"})
            (root / "web" / "public" / "output" / "data").mkdir(parents=True)

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("mirror_missing", {issue.code for issue in result.issues})

    def test_detects_merge_conflict_marker_in_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            source.mkdir(parents=True)
            mirror.mkdir(parents=True)
            (source / "price_history.csv").write_text("date,ticker\n<<<<<<< HEAD\n", encoding="utf-8")

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("merge_conflict_marker", {issue.code for issue in result.issues})

    def test_passes_when_source_and_web_public_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "index.json", {"schema_version": 1, "tickers": []})
            _write_json(root / "web" / "public" / "output" / "data" / "index.json", {"schema_version": 1, "tickers": []})
            _write_json(root / "output" / "data" / "tickers" / "AAPL" / "latest.json", {"ticker": "AAPL"})
            _write_json(root / "web" / "public" / "output" / "data" / "tickers" / "AAPL" / "latest.json", {"ticker": "AAPL"})

            result = check_output_health(root)

        self.assertTrue(result.ok, result.format_summary())

    def test_search_evidence_is_part_of_default_web_mirror_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(
                root / "output" / "data" / "search_evidence.json",
                {"schema_version": 1, "date": "2026-05-07", "items": [], "by_ticker": {}, "run_summary": {}},
            )
            (root / "web" / "public" / "output" / "data").mkdir(parents=True)

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("mirror_missing", {issue.code for issue in result.issues})

    def test_cli_returns_nonzero_when_health_check_fails(self) -> None:
        from src.cli.output_health_check import main

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            source.mkdir(parents=True)
            mirror.mkdir(parents=True)
            (source / "index.json").write_text('{"schema_version": ', encoding="utf-8")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(["--project-root", str(root)])

        self.assertEqual(exit_code, 1)
        self.assertIn("invalid_json", stdout.getvalue())
