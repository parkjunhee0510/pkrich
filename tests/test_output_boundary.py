"""Enforce output/ layer boundary: no direct database or derivation imports."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "src" / "output"

# output/ modules must not import these — derivation & storage concerns
# belong to analyzer/derive or utils/datastore. Orchestration (pipeline,
# markdown) precomputes and passes data as kwargs.
FORBIDDEN_MODULES = {
    "sqlite3",
    "src.backtester.engine",
    "src.utils.earnings_history",
    "src.utils.earnings_pattern",
    "src.utils.earnings_setup",
    "src.utils.monthly_summary",
    "src.utils.ticker_timelines",
    "src.utils.sec_filings",
}

# markdown.py is the orchestration entry for output/ — it precomputes
# derivations via analyzer/derive. json_export should stay pure.
STRICT_FILES = {"json_export.py"}


class OutputBoundaryTests(unittest.TestCase):
    def test_json_export_has_no_forbidden_imports(self) -> None:
        for py_file in OUTPUT_DIR.glob("*.py"):
            if py_file.name not in STRICT_FILES:
                continue
            tree = ast.parse(py_file.read_text(encoding="utf-8-sig"))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)

            offenders = imported & FORBIDDEN_MODULES
            self.assertFalse(
                offenders,
                f"{py_file.name} imports forbidden modules: {sorted(offenders)}. "
                "Derivations/storage must be precomputed and passed as kwargs.",
            )


if __name__ == "__main__":
    unittest.main()
