from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HOOK = Path(__file__).resolve().parents[1] / ".codex" / "hooks" / "summarize_session.py"


class SummarizeSessionHookTests(unittest.TestCase):
    def make_repo(self) -> tempfile.TemporaryDirectory[str]:
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        (root / "AGENTS.md").write_text("# test repo\n", encoding="utf-8")
        (root / ".codex").mkdir()
        subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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

    def test_writes_handoff_when_available(self) -> None:
        with self.make_repo() as temp_dir:
            root = Path(temp_dir)

            result = self.run_hook(root, {"last_assistant_message": "summary"})

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(json.loads(result.stdout), {})
            self.assertIn("summary", (root / ".codex" / "handoff.md").read_text(encoding="utf-8"))

    def test_exits_successfully_when_handoff_write_fails(self) -> None:
        with self.make_repo() as temp_dir:
            root = Path(temp_dir)
            handoff = root / ".codex" / "handoff.md"
            handoff.mkdir()

            result = self.run_hook(root, {"last_assistant_message": "summary"})

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(json.loads(result.stdout), {})

            os.chmod(handoff, stat.S_IWRITE)

    def test_exits_quickly_without_stdin_payload(self) -> None:
        with self.make_repo() as temp_dir:
            root = Path(temp_dir)

            result = subprocess.run(
                [sys.executable, str(HOOK)],
                stdin=subprocess.DEVNULL,
                text=True,
                capture_output=True,
                cwd=root,
                check=False,
                timeout=2,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(json.loads(result.stdout), {})

    def test_exits_when_stdin_pipe_stays_open_without_payload(self) -> None:
        with self.make_repo() as temp_dir:
            root = Path(temp_dir)

            process = subprocess.Popen(
                [sys.executable, str(HOOK)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=root,
            )
            try:
                process.wait(timeout=2)
                stdout = process.stdout.read() if process.stdout else ""
                stderr = process.stderr.read() if process.stderr else ""
            finally:
                if process.stdin:
                    process.stdin.close()

            self.assertEqual(process.returncode, 0, msg=stderr)
            self.assertEqual(json.loads(stdout), {})


if __name__ == "__main__":
    unittest.main()
