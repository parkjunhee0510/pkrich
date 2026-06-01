"""CLI for backfilling legacy signal tracker decision metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from src.utils.signal_metadata_backfill import backfill_signal_metadata_file


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill output/data/signal_tracker.csv with finalized decision metadata.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Repository root containing output/data.",
    )
    parser.add_argument(
        "--signal-csv",
        default=None,
        help="Override path to signal_tracker.csv.",
    )
    parser.add_argument(
        "--dashboard-history",
        default=None,
        help="Override path to dashboard_history.json.",
    )
    parser.add_argument(
        "--latest-index",
        default=None,
        help="Override path to index.json.",
    )
    args = parser.parse_args(argv)

    project_root = Path(args.project_root)
    data_dir = project_root / "output" / "data"
    signal_csv = Path(args.signal_csv) if args.signal_csv else data_dir / "signal_tracker.csv"
    dashboard_history = (
        Path(args.dashboard_history)
        if args.dashboard_history
        else data_dir / "dashboard_history.json"
    )
    latest_index = Path(args.latest_index) if args.latest_index else data_dir / "index.json"

    stats = backfill_signal_metadata_file(
        signal_csv,
        dashboard_history,
        latest_index_path=latest_index,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())