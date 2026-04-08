from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from src.types import TickerAnalysis


def write_outputs(analyses: list[TickerAnalysis], run_date: date) -> None:
    output_root = Path("output")
    daily_dir = output_root / "daily"
    tickers_dir = output_root / "tickers"
    data_dir = output_root / "data"

    daily_dir.mkdir(parents=True, exist_ok=True)
    tickers_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    daily_path = daily_dir / f"{run_date.isoformat()}.md"
    daily_path.write_text(render_daily_markdown(analyses, run_date), encoding="utf-8")

    for analysis in analyses:
        ticker_dir = tickers_dir / analysis.ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)
        ticker_path = ticker_dir / f"{run_date.isoformat()}.md"
        ticker_path.write_text(render_ticker_markdown(analysis), encoding="utf-8")

    append_price_history(data_dir / "price_history.csv", analyses)


def render_daily_markdown(analyses: list[TickerAnalysis], run_date: date) -> str:
    watchlist_rows = "\n".join(
        f"| {analysis.ticker} | {analysis.data_snapshot['Price']} | {analysis.data_snapshot['Daily Change']} | {analysis.signal_or_takeaway} |"
        for analysis in analyses
    )
    top_movers = sorted(
        analyses,
        key=lambda item: _numeric_change(item.data_snapshot["Daily Change"]),
        reverse=True,
    )
    top_mover_lines = "\n".join(
        f"- **{analysis.ticker}**: {analysis.summary}"
        for analysis in top_movers[:3]
    ) or "- No movers available."
    action_items = "\n".join(
        f"- [ ] Review {analysis.ticker} for any material update."
        for analysis in analyses
    ) or "- [ ] No action items."

    return "\n".join(
        [
            f"# Daily Research - {run_date.isoformat()}",
            "",
            "## Market Overview",
            "Market overview is derived from collected watchlist data for this run.",
            "",
            "## Watchlist Summary",
            "| Ticker | Price | Change | Signal |",
            "|--------|-------|--------|--------|",
            watchlist_rows or "| N/A | N/A | N/A | N/A |",
            "",
            "## Top Movers",
            top_mover_lines,
            "",
            "## Action Items",
            action_items,
            "",
        ]
    )


def render_ticker_markdown(analysis: TickerAnalysis) -> str:
    return "\n".join(
        [
            f"# {analysis.ticker} - {analysis.date}",
            "",
            "## Summary",
            analysis.summary or "No summary available.",
            "",
            "## Key News",
            _render_bullets(analysis.key_news),
            "",
            "## Financial Highlights",
            _render_bullets(analysis.financial_highlights),
            "",
            "## Risks / Watchpoints",
            _render_bullets(analysis.risks_or_watchpoints),
            "",
            "## Data Snapshot",
            "| Metric | Value |",
            "|--------|-------|",
            *[f"| {key} | {value} |" for key, value in analysis.data_snapshot.items()],
            "",
            "## Signal / Takeaway",
            analysis.signal_or_takeaway or "No takeaway available.",
            "",
        ]
    )


def append_price_history(path: Path, analyses: list[TickerAnalysis]) -> None:
    fieldnames = ["date", "ticker", "price", "daily_change", "market_cap", "trailing_pe"]
    existing_rows: list[dict[str, str]] = []

    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            existing_rows = list(reader)

    updated_rows = [
        row
        for row in existing_rows
        if (row.get("date"), row.get("ticker"))
        not in {(analysis.date, analysis.ticker) for analysis in analyses}
    ]

    updated_rows.extend(
        {
            "date": analysis.date,
            "ticker": analysis.ticker,
            "price": analysis.data_snapshot["Price"],
            "daily_change": analysis.data_snapshot["Daily Change"],
            "market_cap": analysis.data_snapshot["Market Cap"],
            "trailing_pe": analysis.data_snapshot["Trailing P/E"],
        }
        for analysis in analyses
    )

    updated_rows.sort(key=lambda row: (row["date"], row["ticker"]))

    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)


def _render_bullets(items: list[str]) -> str:
    if not items:
        return "- None."
    return "\n".join(f"- {item}" for item in items)


def _numeric_change(raw_value: str) -> float:
    try:
        return float(raw_value.replace("%", ""))
    except ValueError:
        return float("-inf")
