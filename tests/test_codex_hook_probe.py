from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CodexHookProbeTests(unittest.TestCase):
    def test_probe_writes_log_entry_from_hook_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script_path = Path("C:/Users/junhe/OneDrive/문서/pkrich/.codex/hooks/test_pre_tool_use_probe.py")
            log_path = root / ".codex" / "hook-test.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "session_id": "test-session",
                "transcript_path": "session.jsonl",
                "cwd": str(root),
                "tool_name": "shell_command",
                "tool_input": {"command": "Get-ChildItem -Force"},
            }

            result = subprocess.run(
                [sys.executable, str(script_path)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                cwd=root,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(log_path.exists())
            entry = log_path.read_text(encoding="utf-8")
            self.assertIn("shell_command", entry)
            self.assertIn("Get-ChildItem -Force", entry)
            self.assertEqual(json.loads(result.stdout), {})


if __name__ == "__main__":
    unittest.main()
