from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


HOOK = Path(__file__).resolve().parents[1] / ".codex" / "hooks" / "post_edit_validate.py"


class PostEditValidateHookTests(unittest.TestCase):
    def make_repo(self) -> tempfile.TemporaryDirectory[str]:
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        (root / "AGENTS.md").write_text("# test repo\n", encoding="utf-8")
        (root / "main.py").write_text("print('ok')\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "tests").mkdir()
        (root / "tests" / "test_module.py").write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")
        (root / "web").mkdir()
        return temp_dir

    def run_hook(self, root: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=root,
            check=False,
        )

    def test_handles_utf8_lint_output_without_crashing(self) -> None:
        with self.make_repo() as temp_dir:
            root = Path(temp_dir)
            (root / "web" / "package.json").write_text(
                textwrap.dedent(
                    r"""
                    {
                      "scripts": {
                        "lint": "node -e \"process.stdout.write('unicode arrow: \\u2192')\""
                      }
                    }
                    """
                ).strip(),
                encoding="utf-8",
            )

            result = self.run_hook(root, {"tool_input": {"file_path": "web/src/App.tsx"}})

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(json.loads(result.stdout), {})

    def test_skips_validation_for_docs_only_edits(self) -> None:
        with self.make_repo() as temp_dir:
            root = Path(temp_dir)
            (root / "web" / "package.json").write_text(
                textwrap.dedent(
                    r"""
                    {
                      "scripts": {
                        "lint": "node -e \"process.exit(7)\""
                      }
                    }
                    """
                ).strip(),
                encoding="utf-8",
            )

            result = self.run_hook(root, {"tool_input": {"file_path": "docs/note.md"}})

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(json.loads(result.stdout), {})

    def test_unknown_edit_payload_does_not_run_web_lint(self) -> None:
        with self.make_repo() as temp_dir:
            root = Path(temp_dir)
            (root / "web" / "package.json").write_text(
                textwrap.dedent(
                    r"""
                    {
                      "scripts": {
                        "lint": "node -e \"process.exit(7)\""
                      }
                    }
                    """
                ).strip(),
                encoding="utf-8",
            )

            result = self.run_hook(root, {"tool_input": {}})

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(json.loads(result.stdout), {})

    def test_accepts_python_files_with_utf8_bom(self) -> None:
        with self.make_repo() as temp_dir:
            root = Path(temp_dir)
            (root / "src" / "bom_module.py").write_text("\ufeffVALUE = 1\n", encoding="utf-8")

            result = self.run_hook(root, {"tool_input": {"file_path": "src/bom_module.py"}})

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(json.loads(result.stdout), {})


if __name__ == "__main__":
    unittest.main()
