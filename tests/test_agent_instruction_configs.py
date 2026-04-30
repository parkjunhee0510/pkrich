from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_ROLE_DIR = ROOT / ".codex" / "agents"
INSTRUCTION_FILES = [
    ROOT / "AGENTS.md",
    ROOT / "docs" / "codex" / "index.md",
    ROOT / "analyzer" / "AGENTS.md",
    ROOT / "output" / "AGENTS.md",
    ROOT / "src" / "analyzer" / "AGENTS.md",
    ROOT / "src" / "output" / "AGENTS.md",
]


class AgentInstructionConfigTests(unittest.TestCase):
    def test_agent_roles_define_descriptions(self) -> None:
        if not AGENT_ROLE_DIR.exists():
            self.skipTest("local .codex/agents not present in this worktree")

        role_paths = sorted(AGENT_ROLE_DIR.glob("*.toml"))
        self.assertNotEqual(role_paths, [], msg="No agent role TOML files found")

        missing = []
        invalid = []

        for path in role_paths:
            try:
                config = tomllib.loads(path.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as exc:
                invalid.append(f"{path.name}: {exc}")
                continue

            description = config.get("description")
            if not isinstance(description, str) or not description.strip():
                missing.append(path.name)

        self.assertEqual(invalid, [], msg=f"Invalid TOML files: {invalid}")
        self.assertEqual(missing, [], msg=f"Missing descriptions: {missing}")

    def test_instruction_files_exist(self) -> None:
        missing = [str(path.relative_to(ROOT)) for path in INSTRUCTION_FILES if not path.exists()]

        self.assertEqual(missing, [], msg=f"Missing instruction files: {missing}")

    def test_instruction_files_do_not_contain_known_mojibake_markers(self) -> None:
        markers = ["??", "\ufffd"]
        offenders = []

        for path in INSTRUCTION_FILES:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for marker in markers:
                if marker in text:
                    offenders.append(f"{path.relative_to(ROOT)} contains {marker!r}")

        self.assertEqual(offenders, [], msg=f"Mojibake markers found: {offenders}")

    def test_root_agents_does_not_duplicate_codex_task_routing(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        forbidden_fragments = [
            "### Collector work",
            "### Analyzer work",
            "### Output or frontend data work",
        ]
        offenders = [fragment for fragment in forbidden_fragments if fragment in text]

        self.assertEqual(offenders, [], msg=f"Root routing duplication found: {offenders}")

    def test_codex_index_names_scoped_instruction_files(self) -> None:
        text = (ROOT / "docs" / "codex" / "index.md").read_text(encoding="utf-8")

        self.assertIn("nested `AGENTS.md`", text)
        self.assertIn("`src/analyzer/AGENTS.md`", text)
        self.assertIn("`src/output/AGENTS.md`", text)

    def test_output_agents_lists_established_artifact_directories(self) -> None:
        text = (ROOT / "output" / "AGENTS.md").read_text(encoding="utf-8")

        for directory in ["cache", "daily", "data", "tickers"]:
            self.assertIn(f"{directory}/", text)


if __name__ == "__main__":
    unittest.main()
