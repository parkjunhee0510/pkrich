from __future__ import annotations

import os
from typing import Any

from src.utils.env import load_dotenv
from src.utils.model_config import load_model_profile
from src.utils.pipeline_logging import record_pipeline_event


def generate_weekly_insight(
    *,
    iso_year: int,
    iso_week: int,
    start_date: str,
    end_date: str,
    market_moves: list[Any],
    sector_performance: list[Any],
    top_gainers: list[Any],
    top_losers: list[Any],
    repeated_news: list[Any],
    signal_summary: list[str],
    action_items: list[str],
) -> str:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        return ""

    try:
        from openai import OpenAI

        model_profile = load_model_profile()
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.responses.create(
            model=model_profile.model,
            max_output_tokens=min(model_profile.max_output_tokens, 500),
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are a concise weekly market strategist. "
                                "Write 3 short Korean sentences only. "
                                "Sentence 1: summarize the week's market/sector theme with numbers. "
                                "Sentence 2: explain the most important repeated catalyst or signal takeaway. "
                                "Sentence 3: state the next-week watchpoint or risk in a practical tone. "
                                "Use only the provided data and avoid markdown bullets."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": _build_prompt(
                                iso_year=iso_year,
                                iso_week=iso_week,
                                start_date=start_date,
                                end_date=end_date,
                                market_moves=market_moves,
                                sector_performance=sector_performance,
                                top_gainers=top_gainers,
                                top_losers=top_losers,
                                repeated_news=repeated_news,
                                signal_summary=signal_summary,
                                action_items=action_items,
                            ),
                        }
                    ],
                },
            ],
        )
        return getattr(response, "output_text", "").strip()
    except Exception as exc:
        record_pipeline_event(
            "analyzer",
            "warning",
            "weekly_insight_failed",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return ""


def _build_prompt(
    *,
    iso_year: int,
    iso_week: int,
    start_date: str,
    end_date: str,
    market_moves: list[Any],
    sector_performance: list[Any],
    top_gainers: list[Any],
    top_losers: list[Any],
    repeated_news: list[Any],
    signal_summary: list[str],
    action_items: list[str],
) -> str:
    market_lines = ", ".join(f"{item.label} {item.weekly_change}" for item in market_moves[:3]) or "N/A"
    sector_lines = ", ".join(f"{item.sector} {item.average_weekly_change}" for item in sector_performance[:3]) or "N/A"
    gainer_lines = ", ".join(f"{item.ticker} {item.weekly_change}" for item in top_gainers[:3]) or "N/A"
    loser_lines = ", ".join(f"{item.ticker} {item.weekly_change}" for item in top_losers[:3]) or "N/A"
    news_lines = ", ".join(f"{item.summary} ({item.count}회)" for item in repeated_news[:3]) or "N/A"
    signals = "; ".join(signal_summary[:3]) or "N/A"
    actions = "; ".join(action_items[:4]) or "N/A"

    return (
        f"Week: {iso_year}-W{iso_week:02d} ({start_date} to {end_date})\n"
        f"Market: {market_lines}\n"
        f"Sectors: {sector_lines}\n"
        f"Top Gainers: {gainer_lines}\n"
        f"Top Losers: {loser_lines}\n"
        f"Repeated News: {news_lines}\n"
        f"Signal Summary: {signals}\n"
        f"Action Items: {actions}"
    )
