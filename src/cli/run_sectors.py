"""Standalone entry point for the sector explorer scan.

Runs just the sector collector + JSON exporter without the full daily pipeline.
Useful when iterating on `config/sectors.yaml` or when you only need to refresh
the `/sectors` page without touching analyzer / decision layers.

Usage:
    python -m src.cli.run_sectors                  # normal: dedupe vs watchlist
    python -m src.cli.run_sectors --all            # ignore watchlist dedup
    python -m src.cli.run_sectors --no-sync        # skip web/public copy
    python -m src.cli.run_sectors --sectors space quantum  # filter by id
    python -m src.cli.run_sectors --date 2025-04-19
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from src.collector.sector_scan import scan_sectors
from src.output.json_export import _sync_web_public_data
from src.output.sectors_json import write_sectors_json
from src.utils.config import load_sectors, load_watchlist
from src.utils.pipeline_logging import record_pipeline_event


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the sector explorer scan only (no analyzer, no decision)."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Do not skip watchlist overlaps -- fetch every sector ticker fresh.",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip syncing output/data/sectors.json into web/public.",
    )
    parser.add_argument(
        "--sectors",
        nargs="*",
        metavar="ID",
        help="Only scan the given sector ids (matches `id:` in config/sectors.yaml).",
    )
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="Override the run date stamped into sectors.json (default: today).",
    )
    args = parser.parse_args()

    run_date = date.fromisoformat(args.date) if args.date else date.today()

    sectors_config = load_sectors()
    if not sectors_config:
        raise SystemExit(
            "No sectors configured -- check config/sectors.yaml for parse errors."
        )

    if args.sectors:
        wanted = {sid.lower() for sid in args.sectors}
        sectors_config = [s for s in sectors_config if s.id in wanted]
        if not sectors_config:
            raise SystemExit(
                f"No matching sectors for filter {sorted(wanted)}. "
                f"Available: {[s.id for s in load_sectors()]}"
            )

    skip_tickers: set[str] = set()
    if not args.all:
        try:
            watchlist = load_watchlist()
            skip_tickers = {item.ticker.upper() for item in watchlist}
        except Exception as exc:  # noqa: BLE001 -- defensive, keep scanning
            print(f"Warning: could not load watchlist ({exc!s}); scanning all.")

    total_tickers = sum(len(s.tickers) for s in sectors_config)
    print(
        f"Scanning {len(sectors_config)} sector(s) / "
        f"{total_tickers} ticker(s)"
        + (f" -- skipping {len(skip_tickers)} watchlist overlap(s)" if skip_tickers else "")
        + "..."
    )

    snapshots = scan_sectors(sectors_config, run_date, skip_tickers=skip_tickers)

    output_root = Path("output")
    path = write_sectors_json(snapshots, run_date, output_root=output_root)
    print(f"Wrote {path} ({path.stat().st_size / 1024:.1f} KB)")

    if not args.no_sync:
        # data_dir = <repo>/output/data  →  project_root = <repo>
        _sync_web_public_data(output_root / "data", Path("."))
        print("Synced to web/public/output/data/")

    record_pipeline_event(
        "cli",
        "info",
        "sector_scan_standalone_completed",
        sector_count=len(snapshots),
        ticker_count=total_tickers,
    )


if __name__ == "__main__":
    main()
