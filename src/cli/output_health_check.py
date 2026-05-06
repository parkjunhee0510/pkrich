"""CLI for validating generated output artifacts and web mirrors."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from src.output.health_check import check_output_health


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate output/data JSON files and web/public output mirror consistency.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Repository root containing output/data and web/public/output/data.",
    )
    args = parser.parse_args(argv)

    result = check_output_health(Path(args.project_root))
    print(result.format_summary())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
