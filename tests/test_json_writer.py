from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.output.json_writer import JsonWriteError, write_json_file


class JsonWriterTests(unittest.TestCase):
    def test_write_json_file_round_trips_escaped_unicode_newlines_and_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "output" / "data" / "sample.json"
            payload = {
                "schema_version": 1,
                "message": "\ud55c\uad6d\uc5b4 line\nwith \"quotes\" and backslash \\",
            }

            write_json_file(path, payload)

            loaded = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(loaded, payload)

    def test_write_json_file_rejects_non_serializable_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"

            with self.assertRaises(JsonWriteError):
                write_json_file(path, {"bad": object()})

            self.assertFalse(path.exists())

    def test_write_json_file_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / "payload.json"

            write_json_file(path, {"schema_version": 1})

            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
