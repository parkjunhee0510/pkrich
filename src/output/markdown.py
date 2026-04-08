from __future__ import annotations

import csv
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from src.types import TickerAnalysis
from src.utils.config import load_simple_mapping


_DEFAULT_SOURCE_PRIORITIES = {
    "reuters": 5,
    "associated press": 4,
    "ap": 4,
    "bloomberg": 3,
    "yahoo finance": 2,
    "seeking alpha": 1,
    "duckduckgo": 0,
    "rss": 0,
    "fallback": -1,
}
_DEFAULT_SECTOR_DISPLAY_ORDER = [
    "Technology",
    "Semiconductors",
    "Healthcare",
    "Financials",
    "Energy",
    "Consumer Discretionary",
    "Consumer Staples",
    "Industrials",
    "Communication Services",
    "Utilities",
    "Real Estate",
    "Materials",
]


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
    top_news_links = _render_daily_news_links(analyses)
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
            "## Top News Links",
            top_news_links,
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
            _render_news_items(analysis),
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


def _render_news_items(analysis: TickerAnalysis) -> str:
    if analysis.news_references:
        return "\n".join(_render_news_line(item) for item in analysis.news_references)
    return _render_bullets(analysis.key_news)


def _render_daily_news_links(analyses: list[TickerAnalysis]) -> str:
    grouped: dict[str, list[tuple[tuple[datetime, int], str, str]]] = {}
    hide_fallback_without_links = _hide_fallback_news_without_links()
    for analysis in analyses:
        sector = analysis.data_snapshot.get("Sector", "N/A")
        if analysis.news_references:
            visible_news = [
                item
                for item in analysis.news_references
                if not (
                    hide_fallback_without_links
                    and not item.link
                    and (item.source or "").strip().lower() == "fallback"
                )
            ]
            if not visible_news:
                continue
            first_news = sorted(
                visible_news,
                key=lambda item: (_news_sort_key(item.published_at), _source_priority(item.source)),
                reverse=True,
            )[0]
            line = f"- **{analysis.ticker}**: {_render_news_line(first_news)[2:]}"
            sort_key = (_news_sort_key(first_news.published_at), _source_priority(first_news.source))
        elif analysis.key_news:
            line = f"- **{analysis.ticker}**: {analysis.key_news[0]}"
            sort_key = (_news_sort_key(""), _source_priority(""))
        else:
            continue
        grouped.setdefault(sector, []).append((sort_key, analysis.ticker, line))

    if not grouped:
        return "- No news links available."

    sections: list[str] = []
    for sector in _ordered_sectors(grouped):
        sections.append(f"### {sector}")
        ordered_lines = sorted(
            grouped[sector],
            key=lambda entry: (entry[0][0], entry[0][1], entry[1]),
            reverse=True,
        )
        sections.extend(entry[2] for entry in ordered_lines)
        sections.append("")
    return "\n".join(sections).rstrip()


def _render_news_line(item) -> str:
    source = item.source or "Source"
    published_suffix = f" ({item.published_at})" if item.published_at else ""
    if item.link:
        return f"- [{item.title}]({item.link}) - {source}{published_suffix}"
    return f"- {item.title} - {source}{published_suffix}"


def _numeric_change(raw_value: str) -> float:
    try:
        return float(raw_value.replace("%", ""))
    except ValueError:
        return float("-inf")


def _news_sort_key(raw_value: str) -> datetime:
    if not raw_value:
        return datetime.min

    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass

    try:
        return parsedate_to_datetime(raw_value).replace(tzinfo=None)
    except (TypeError, ValueError):
        return datetime.min


def _source_priority(source: str) -> int:
    normalized = (source or "").strip().lower()
    priorities = _load_source_priorities()
    return priorities.get(normalized, 0)


def _load_source_priorities() -> dict[str, int]:
    try:
        raw_config = load_simple_mapping("config/output.yaml")
        configured = raw_config.get("news_source_priority", {})
        if not isinstance(configured, dict):
            return _DEFAULT_SOURCE_PRIORITIES
        return {
            str(key).strip().lower(): int(value)
            for key, value in configured.items()
        }
    except Exception:
        return _DEFAULT_SOURCE_PRIORITIES


def _hide_fallback_news_without_links() -> bool:
    try:
        raw_config = load_simple_mapping("config/output.yaml")
        configured = raw_config.get("hide_fallback_news_without_links")
        if isinstance(configured, bool):
            return configured
        return True
    except Exception:
        return True


def _ordered_sectors(grouped: dict[str, list[tuple[tuple[datetime, int], str, str]]]) -> list[str]:
    configured_order = _load_sector_display_order()
    order_map = {sector: index for index, sector in enumerate(configured_order)}
    return sorted(grouped, key=lambda sector: (order_map.get(sector, len(order_map)), sector))


def _load_sector_display_order() -> list[str]:
    try:
        raw_config = load_simple_mapping("config/output.yaml")
        configured = raw_config.get("sector_display_order")
        if not isinstance(configured, list):
            return _DEFAULT_SECTOR_DISPLAY_ORDER
        return [str(item) for item in configured if str(item).strip()]
    except Exception:
        return _DEFAULT_SECTOR_DISPLAY_ORDER
